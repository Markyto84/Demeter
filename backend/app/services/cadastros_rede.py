"""Comandos administrativos com comparação de base e recibo transacional local."""
from copy import deepcopy
import json
import secrets
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload, undefer

from ..core.security import hash_senha
from ..core.sessoes import revogar_sessoes
from ..models.models import ConfiguracaoOperacional, Dieta, Filial, FormularioConfig, ImpressoraEtiqueta, Perfil, Usuario
from ..models.rede import AlteracaoCadastroRemota, AplicacaoCadastroLocal
from ..schemas.schemas import DietaCreate, FormularioConfigUpdate, ImpressoraEtiquetaUpdate, ImpressoraUpdate, UsuarioCreate, UsuarioUpdate
from .email_medico import cifra
from .protocolo_rede import canonico, resumo_sha
from .validacao_pedidos import validar_esquema
from .liquido_espessado import formulario_liquidos


class AlteracaoRemota(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    entidade: str = Field(max_length=100)
    base_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    dados: dict
    motivo: str = Field(min_length=8, max_length=500)


class Prazos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preparo_minutos: int | None = Field(ge=1, le=1440)
    entrega_minutos: int | None = Field(ge=1, le=1440)


class DietaRemota(DietaCreate):
    ativa: bool = True


def validar_dados(entidade, dados):
    grupo, _, chave = entidade.partition(":")
    if grupo == "dieta" and (chave == "nova" or chave.isdigit()): return DietaRemota.model_validate(dados).model_dump()
    if grupo == "formulario" and chave in ("MEDICO", "ENFERMAGEM"):
        config = FormularioConfigUpdate.model_validate(dados)
        config.esquema_json = formulario_liquidos(config.esquema_json)
        validar_esquema(config.esquema_json)
        return {"esquema_json": config.esquema_json}
    if entidade == "prazos": return Prazos.model_validate(dados).model_dump()
    if entidade == "impressora": return ImpressoraUpdate.model_validate(dados).model_dump()
    if entidade == "etiquetas": return ImpressoraEtiquetaUpdate.model_validate(dados).model_dump()
    if grupo == "usuario" and chave:
        modelo = UsuarioCreate if chave == "novo" else UsuarioUpdate
        valor = modelo.model_validate(dados)
        if valor.filial_ids: raise HTTPException(422, "O vínculo da credencial será a própria unidade")
        if chave != "novo" and (valor.nome_usuario != chave or valor.senha is not None):
            raise HTTPException(422, "Renomear ou redefinir senha de conta existente exige acesso direto à unidade")
        return valor.model_dump()
    raise HTTPException(422, "Cadastro remoto não reconhecido")


async def capturar(db, filial_id):
    filial = await db.get(Filial, filial_id)
    dados = {"dieta:nova": None, "usuario:novo": None, "impressora": {"ip_impressora": filial.ip_impressora}}
    for dieta in (await db.scalars(select(Dieta).where(Dieta.filial_id == filial_id).order_by(Dieta.id))).all():
        dados[f"dieta:{dieta.id}"] = {k: getattr(dieta, k) for k in ("nome", "descricao", "severa", "ativa")}
    for tipo in ("MEDICO", "ENFERMAGEM"):
        config = await db.scalar(select(FormularioConfig).where(FormularioConfig.filial_id == filial_id, FormularioConfig.tipo_publico == tipo))
        dados[f"formulario:{tipo}"] = {"esquema_json": config.esquema_json} if config else None
    prazos = await db.get(ConfiguracaoOperacional, filial_id)
    dados["prazos"] = {"preparo_minutos": prazos.preparo_minutos, "entrega_minutos": prazos.entrega_minutos} if prazos else None
    etiqueta = await db.get(ImpressoraEtiqueta, filial_id)
    dados["etiquetas"] = {k: getattr(etiqueta, k) for k in ("modelo", "ip", "porta", "protocolo", "resolucao", "intervalo_mm")} if etiqueta else None
    usuarios = (await db.scalars(select(Usuario).options(selectinload(Usuario.perfil)).order_by(Usuario.nome_usuario))).all()
    for usuario in usuarios:
        dados["usuario:" + usuario.nome_usuario] = {"nome": usuario.nome, "nome_usuario": usuario.nome_usuario, "perfil": usuario.perfil.nome,
            "origem_autenticacao": usuario.origem_autenticacao, "usuario_ad": usuario.usuario_ad, "ativo": usuario.ativo}
    return deepcopy(dados)


def conferir_acesso(entidade, perfil):
    if perfil != "ADMIN_TI" and not (entidade.startswith("dieta:") or entidade.startswith("formulario:") or entidade == "prazos"):
        raise HTTPException(403, "Este cadastro exige o perfil de administrador de TI")


def dto(comando):
    return {k: getattr(comando, k) for k in ("id", "entidade", "base_sha256", "autor_nome", "autor_perfil", "estado", "motivo", "resultado", "criado_em", "concluido_em")}


async def comandos_pendentes(db, servidor_id):
    comandos = (await db.scalars(select(AlteracaoCadastroRemota).options(undefer(AlteracaoCadastroRemota.dados_cifrados))
        .where(AlteracaoCadastroRemota.servidor_id == servidor_id, AlteracaoCadastroRemota.estado == "PENDENTE")
        .order_by(AlteracaoCadastroRemota.criado_em).limit(5))).all()
    return [{"id": c.id, "entidade": c.entidade, "base_sha256": c.base_sha256, "autor_nome": c.autor_nome,
        "dados": json.loads(cifra().decrypt(c.dados_cifrados.encode("ascii")))} for c in comandos]


async def aplicar(db, filial_id, comando):
    anterior = await db.get(AplicacaoCadastroLocal, comando["id"])
    if anterior: return anterior
    entidade = comando["entidade"]
    grupo, _, chave = entidade.partition(":")
    # Mesma ordem dos bloqueios usados pelos editores locais.
    if grupo == "dieta" and chave != "nova":
        await db.scalar(select(Dieta).where(Dieta.id == int(chave), Dieta.filial_id == filial_id).with_for_update())
    elif grupo == "usuario" and chave != "novo":
        await db.scalar(select(Usuario).where(Usuario.nome_usuario == chave).with_for_update())
    else:
        await db.scalar(select(Filial).where(Filial.id == filial_id).with_for_update())
    atuais = await capturar(db, filial_id)
    antes = atuais.get(entidade)
    recibo = AplicacaoCadastroLocal(id=comando["id"], entidade=entidade, autor_nome=comando["autor_nome"], estado="CONFLITO",
        resultado="Cadastro alterado na unidade. Revise a versão recebida e envie uma nova proposta", antes=antes)
    if resumo_sha(antes) != comando["base_sha256"]:
        db.add(recibo)
        return recibo
    dados = validar_dados(entidade, comando["dados"])
    if grupo == "dieta":
        objeto = await db.get(Dieta, int(chave)) if chave != "nova" else Dieta(filial_id=filial_id)
        if objeto is None or objeto.filial_id != filial_id: raise HTTPException(409, "Dieta não encontrada nesta unidade")
    elif grupo == "formulario":
        objeto = await db.scalar(select(FormularioConfig).where(FormularioConfig.filial_id == filial_id, FormularioConfig.tipo_publico == chave))
        objeto = objeto or FormularioConfig(filial_id=filial_id, tipo_publico=chave)
    elif entidade == "prazos": objeto = await db.get(ConfiguracaoOperacional, filial_id) or ConfiguracaoOperacional(filial_id=filial_id)
    elif entidade == "etiquetas": objeto = await db.get(ImpressoraEtiqueta, filial_id) or ImpressoraEtiqueta(filial_id=filial_id)
    elif entidade == "impressora": objeto = await db.get(Filial, filial_id)
    elif grupo == "usuario":
        if chave == "novo":
            if await db.scalar(select(Usuario.id).where(Usuario.nome_usuario == dados["nome_usuario"])):
                recibo.resultado = "Nome de usuário já existe na unidade"; db.add(recibo); return recibo
            objeto = Usuario(nome_usuario=dados["nome_usuario"], senha_hash=hash_senha(dados["senha"] or secrets.token_urlsafe(32)),
                troca_senha_obrigatoria=dados["origem_autenticacao"] == "LOCAL")
        else:
            objeto = await db.scalar(select(Usuario).options(selectinload(Usuario.perfil)).where(Usuario.nome_usuario == chave))
            if objeto is None: raise HTTPException(409, "Usuário não encontrado")
            if objeto.origem_autenticacao != dados["origem_autenticacao"] or objeto.usuario_ad != dados["usuario_ad"]:
                raise HTTPException(409, "Altere a origem de autenticação diretamente na unidade")
            if objeto.perfil.nome == "ADMIN_TI" and objeto.ativo and objeto.origem_autenticacao == "LOCAL" and (not dados["ativo"] or dados["perfil"] != "ADMIN_TI"):
                admins = (await db.scalars(select(Usuario).join(Perfil).where(Perfil.nome == "ADMIN_TI", Usuario.ativo.is_(True), Usuario.origem_autenticacao == "LOCAL")
                    .order_by(Usuario.id).with_for_update(of=Usuario))).all()
                if len(admins) <= 1: raise HTTPException(409, "Mantenha um administrador local ativo")
            await revogar_sessoes(db, objeto.id)
        perfil = await db.scalar(select(Perfil).where(Perfil.nome == dados.pop("perfil")))
        if perfil is None: raise HTTPException(409, "Perfil não disponível na instalação")
        filial = await db.get(Filial, filial_id)
        objeto.perfil = perfil
        objeto.filiais = [filial]
        dados.pop("senha", None); dados.pop("filial_ids", None)
    for campo, valor in dados.items(): setattr(objeto, campo, valor)
    db.add(objeto); await db.flush()
    recibo.estado, recibo.resultado = "APLICADA", "Alteração aplicada na unidade"
    # Nunca guardar senhas, hashes de senha ou material de autenticação no recibo.
    recibo.depois = {k: v for k, v in dados.items() if k != "senha"}
    db.add(recibo)
    return recibo
