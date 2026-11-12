"""Administração da rede e protocolo autenticado entre servidores."""
from datetime import timedelta, timezone
import json
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer
from uuid import uuid4

from ..core.config import settings
from ..core.database import get_db
from ..core.endereco_publico import normalizar_endereco_publico
from ..core.security import exigir_perfis, verificar_acesso_filial
from ..models.models import Filial, Usuario
from ..models.rede import AlteracaoCadastroRemota, EstadoUnidadeLocal, FotoConsolidada, PedidoConsolidado, PublicacaoPedido, ServidorUnidade, VersaoConsolidada
from ..services import cadastros_rede as cadastros
from ..services.email_medico import cifra
from ..services.liquido_espessado import estrutura_formulario
from ..services.protocolo_rede import canonico, resumo_sha
from ..services import central_unidades as central
from ..services.agente_unidade import pendencias
from ..services.auditoria import registrar
from ..services.protocolo_rede import ContatoUnidade, LotePedidos, MAX_LOTE_BYTES

router = APIRouter(prefix="/api", tags=["Servidores das unidades"])
ADMIN = exigir_perfis("ADMIN_TI")
GESTAO = exigir_perfis("ADMIN_TI", "NUTRICIONISTA")


class CadastroServidor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filial_id: int = Field(gt=0)
    url_local: str = Field(max_length=300)
    intervalo_segundos: int = Field(default=60, ge=15, le=3600)

    @field_validator("url_local")
    @classmethod
    def endereco(cls, valor):
        return normalizar_endereco_publico(valor, permitir_local=False)


class Motivo(BaseModel):
    motivo: str = Field(min_length=8, max_length=500)


class IntervaloServidor(Motivo):
    intervalo_segundos: int = Field(ge=15, le=3600)


class CursoresPedido(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instalacao_uuid: UUID
    geracao: int = Field(ge=1)
    pedidos: list[UUID] = Field(max_length=200)


async def unidade_autenticada(request: Request, servidor_id: UUID, db: AsyncSession = Depends(get_db)):
    # O protocolo de replicação nunca é aceito sem TLS em produção.
    if settings.APP_ENV == "production" and request.url.scheme != "https":
        raise HTTPException(426, "Use HTTPS para sincronizar as unidades")
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Credencial de unidade necessária")
    return await central.autenticar_servidor(db, str(servidor_id), authorization[7:])


async def ler_json_limitado(request):
    dados = bytearray()
    async for bloco in request.stream():
        dados.extend(bloco)
        if len(dados) > MAX_LOTE_BYTES:
            raise HTTPException(413, "Lote de sincronização excede o limite")
    try:
        return json.loads(dados)
    except (ValueError, RecursionError):
        raise HTTPException(422, "JSON de sincronização inválido") from None


def validar(modelo, dados):
    try:
        return modelo.model_validate(dados)
    except ValidationError:
        raise HTTPException(422, "Os dados não correspondem ao protocolo de sincronização") from None


@router.get("/rede/disponibilidade")
async def disponibilidade(db: AsyncSession = Depends(get_db)):
    estado = await db.get(EstadoUnidadeLocal, 1) if settings.MODO_SERVIDOR == "UNIDADE" else None
    return {"modo": settings.MODO_SERVIDOR, "operacao_local": bool(estado and estado.operacao_ativada),
        "central_disponivel": bool(estado and estado.ultimo_contato and estado.ultimo_contato > central.agora() - timedelta(seconds=3 * estado.intervalo_segundos + 30))}


@router.get("/rede/estado")
async def estado_local(db: AsyncSession = Depends(get_db), _: Usuario = Depends(GESTAO)):
    estado = await db.get(EstadoUnidadeLocal, 1)
    total, conflitos = await pendencias(db) if estado else (0, 0)
    return {**await disponibilidade(db), "servidor_id": estado.servidor_id if estado else None,
        "pedidos_pendentes": total, "conflitos": conflitos, "ultimo_contato": estado.ultimo_contato.replace(tzinfo=timezone.utc).isoformat() if estado and estado.ultimo_contato else None,
        "ultima_publicacao": estado.ultima_publicacao.replace(tzinfo=timezone.utc).isoformat() if estado and estado.ultima_publicacao else None,
        "ultimo_erro": estado.ultimo_erro if estado else None, "cadastros": "LOCAL"}


@router.post("/rede/tentar-novamente")
async def tentar_novamente(db: AsyncSession = Depends(get_db), _: Usuario = Depends(ADMIN)):
    if settings.MODO_SERVIDOR != "UNIDADE":
        raise HTTPException(409, "Esta função pertence ao servidor da unidade")
    await db.execute(update(PublicacaoPedido).values(tentar_apos=None))
    await db.commit()
    return {"agendado": True}


@router.get("/admin/servidores-unidades")
async def listar(db: AsyncSession = Depends(get_db), _: Usuario = Depends(ADMIN)):
    central.exigir_central()
    linhas = (await db.execute(select(ServidorUnidade, Filial.nome, Filial.codigo_slug).join(Filial)
        .order_by(Filial.nome))).all()
    faltas = dict((await db.execute(select(PedidoConsolidado.servidor_id, func.count())
        .outerjoin(FotoConsolidada, (FotoConsolidada.servidor_id == PedidoConsolidado.servidor_id) & (FotoConsolidada.sha256 == PedidoConsolidado.foto_sha256))
        .where(PedidoConsolidado.foto_sha256.is_not(None), FotoConsolidada.sha256.is_(None)).group_by(PedidoConsolidado.servidor_id))).all())
    return [{**central.dados_servidor(no), "unidade": nome, "codigo_slug": slug, "fotos_pendentes": faltas.get(no.id, 0),
        "conectado": bool(no.ultimo_contato and no.ultimo_contato > central.agora() - timedelta(seconds=3 * no.intervalo_segundos + 30))}
        for no, nome, slug in linhas]


async def servidor_permitido(db, servidor_id, usuario):
    central.exigir_central()
    no = await db.get(ServidorUnidade, str(servidor_id))
    if no is None: raise HTTPException(404, "Servidor não encontrado")
    await verificar_acesso_filial(no.filial_id, usuario, db)
    return no


@router.get("/rede/cadastros/{servidor_id}")
async def consultar_cadastros(servidor_id: UUID, db: AsyncSession = Depends(get_db), usuario: Usuario = Depends(GESTAO)):
    no = await servidor_permitido(db, servidor_id, usuario)
    dados = no.cadastros or {}
    if usuario.perfil.nome != "ADMIN_TI":
        dados = {k: v for k, v in dados.items() if k.startswith(("dieta:", "formulario:")) or k == "prazos"}
    comandos = (await db.scalars(select(AlteracaoCadastroRemota).where(AlteracaoCadastroRemota.servidor_id == no.id)
        .order_by(AlteracaoCadastroRemota.criado_em.desc()).limit(100))).all()
    return {"cadastros": dados, "bases": {k: resumo_sha(v) for k, v in dados.items()}, "recebidos_em": no.cadastros_em, "alteracoes": [cadastros.dto(c) for c in comandos
        if usuario.perfil.nome == "ADMIN_TI" or c.entidade.startswith(("dieta:", "formulario:")) or c.entidade == "prazos"]}


@router.post("/rede/cadastros/{servidor_id}", status_code=202)
async def propor_cadastro(servidor_id: UUID, request: Request, db: AsyncSession = Depends(get_db), usuario: Usuario = Depends(GESTAO)):
    no = await servidor_permitido(db, servidor_id, usuario)
    no = await db.scalar(select(ServidorUnidade).where(ServidorUnidade.id == no.id).with_for_update())
    if not no.credencial_ativa or not no.cadastros:
        raise HTTPException(409, "Conecte a unidade e aguarde o recebimento dos cadastros")
    proposta = validar(cadastros.AlteracaoRemota, await ler_json_limitado(request))
    cadastros.conferir_acesso(proposta.entidade, usuario.perfil.nome)
    if proposta.entidade not in no.cadastros or resumo_sha(no.cadastros[proposta.entidade]) != proposta.base_sha256:
        raise HTTPException(409, "A base foi atualizada. Recarregue os cadastros antes de editar")
    if await db.scalar(select(AlteracaoCadastroRemota.id).where(AlteracaoCadastroRemota.servidor_id == no.id,
        AlteracaoCadastroRemota.entidade == proposta.entidade, AlteracaoCadastroRemota.estado == "PENDENTE").limit(1)):
        raise HTTPException(409, "Já existe alteração pendente para este cadastro. Aguarde sua confirmação")
    try:
        dados = cadastros.validar_dados(proposta.entidade, proposta.dados)
    except ValidationError:
        raise HTTPException(422, "Confira os campos do cadastro. Senhas temporárias devem seguir a regra da aplicação") from None
    if proposta.entidade.startswith("formulario:") and usuario.perfil.nome != "ADMIN_TI":
        antes = no.cadastros[proposta.entidade]
        if not antes or estrutura_formulario(antes["esquema_json"]) != estrutura_formulario(dados["esquema_json"]):
            raise HTTPException(403, "A estrutura dos campos é administrada pela TI")
    comando = AlteracaoCadastroRemota(id=str(uuid4()), servidor_id=no.id, entidade=proposta.entidade, base_sha256=proposta.base_sha256,
        dados_cifrados=cifra().encrypt(canonico(dados)).decode("ascii"), autor_nome=usuario.nome, autor_perfil=usuario.perfil.nome,
        motivo=proposta.motivo)
    db.add(comando)
    registrar(db, usuario, "CADASTRO_REMOTO", no.filial_id, no.filial_id, None,
        {"comando_id": comando.id, "entidade": proposta.entidade, "motivo": proposta.motivo}, "PROPOR")
    await db.commit()
    return cadastros.dto(comando)


@router.post("/admin/servidores-unidades", status_code=201)
async def criar(dados: CadastroServidor, db: AsyncSession = Depends(get_db), usuario: Usuario = Depends(ADMIN)):
    no, arquivo = await central.registrar_servidor(db, dados.filial_id, dados.url_local, dados.intervalo_segundos)
    registrar(db, usuario, "SERVIDOR_UNIDADE", no.filial_id, no.filial_id, None,
        {"servidor_id": no.id, "url_local": no.url_local}, "CRIAR")
    await db.commit()
    return {"servidor": central.dados_servidor(no), "vinculo": arquivo}


@router.post("/admin/servidores-unidades/{servidor_id}/ativar")
async def ativar(servidor_id: UUID, dados: Motivo, db: AsyncSession = Depends(get_db), usuario: Usuario = Depends(ADMIN)):
    no = await central.ativar_servidor(db, str(servidor_id))
    registrar(db, usuario, "SERVIDOR_UNIDADE", no.filial_id, no.filial_id, None,
        {"servidor_id": no.id, "operacao_ativada": True, "motivo": dados.motivo}, "ATIVAR")
    await db.commit()
    return central.dados_servidor(no)


@router.patch("/admin/servidores-unidades/{servidor_id}")
async def ajustar_intervalo(servidor_id: UUID, dados: IntervaloServidor, db: AsyncSession = Depends(get_db), usuario: Usuario = Depends(ADMIN)):
    central.exigir_central()
    no = await db.scalar(select(ServidorUnidade).where(ServidorUnidade.id == str(servidor_id)).with_for_update())
    if no is None: raise HTTPException(404, "Servidor não encontrado")
    antes = no.intervalo_segundos
    no.intervalo_segundos = dados.intervalo_segundos
    registrar(db, usuario, "SERVIDOR_UNIDADE", no.filial_id, no.filial_id, {"intervalo_segundos": antes},
        {"intervalo_segundos": dados.intervalo_segundos, "motivo": dados.motivo}, "INTERVALO")
    await db.commit()
    return central.dados_servidor(no)


@router.post("/admin/servidores-unidades/{servidor_id}/credencial/{acao}")
async def credencial(servidor_id: UUID, acao: str, dados: Motivo, db: AsyncSession = Depends(get_db), usuario: Usuario = Depends(ADMIN)):
    central.exigir_central()
    if acao not in ("renovar", "revogar"):
        raise HTTPException(404, "Ação não encontrada")
    no = await db.scalar(select(ServidorUnidade).where(ServidorUnidade.id == str(servidor_id)).with_for_update())
    if no is None:
        raise HTTPException(404, "Servidor não encontrado")
    token = secrets.token_urlsafe(48) if acao == "renovar" else None
    if token:
        no.token_hash = central.credencial_hash(token)
    no.credencial_ativa = bool(token)
    registrar(db, usuario, "SERVIDOR_UNIDADE", no.filial_id, no.filial_id, None,
        {"servidor_id": no.id, "acao": acao, "motivo": dados.motivo}, "CREDENCIAL")
    await db.commit()
    return {"servidor": central.dados_servidor(no), "vinculo": central.vinculo(no, token) if token else None}


@router.post("/rede/v1/{servidor_id}/contato")
async def contato(request: Request, no: ServidorUnidade = Depends(unidade_autenticada), db: AsyncSession = Depends(get_db)):
    dados = validar(ContatoUnidade, await ler_json_limitado(request))
    retorno = await central.receber_contato(db, no, dados)
    retorno["central_instancia"] = request.app.state.rede_instancia
    await db.commit()
    return retorno


@router.post("/rede/v1/{servidor_id}/estado-publicacoes")
async def cursores(request: Request, no: ServidorUnidade = Depends(unidade_autenticada), db: AsyncSession = Depends(get_db)):
    dados = validar(CursoresPedido, await ler_json_limitado(request))
    central.conferir_instalacao(no, dados.instalacao_uuid, dados.geracao, publicar=True)
    linhas = (await db.execute(select(PedidoConsolidado.pedido_uuid, PedidoConsolidado.sha256, PedidoConsolidado.revisao)
        .where(PedidoConsolidado.servidor_id == no.id, PedidoConsolidado.pedido_uuid.in_([str(uid) for uid in dados.pedidos])))).all()
    return {"pedidos": {uid: {"sha256": digest, "revisao": revisao} for uid, digest, revisao in linhas}}


@router.post("/rede/v1/{servidor_id}/pedidos")
async def publicar(request: Request, no: ServidorUnidade = Depends(unidade_autenticada), db: AsyncSession = Depends(get_db)):
    lote = validar(LotePedidos, await ler_json_limitado(request))
    retorno = await central.receber_lote(db, no, lote)
    await db.commit()
    return retorno


@router.put("/rede/v1/{servidor_id}/pedidos/{pedido_uuid}/foto/{digest}")
async def foto(request: Request, pedido_uuid: UUID, digest: str,
    instalacao: Annotated[UUID, Header(alias="X-Demeter-Instalacao")], geracao: Annotated[int, Header(alias="X-Demeter-Geracao")],
    no: ServidorUnidade = Depends(unidade_autenticada),
    db: AsyncSession = Depends(get_db)):
    central.conferir_instalacao(no, instalacao, geracao, publicar=True)
    dados = bytearray()
    async for bloco in request.stream():
        dados.extend(bloco)
        if len(dados) > 300 * 1024:
            raise HTTPException(413, "O comprovante deve ter até 300 KiB")
    retorno = await central.receber_foto(db, no, pedido_uuid, digest, bytes(dados))
    await db.commit()
    return retorno


@router.get("/relatorios/rede/{servidor_id}/pedidos/{pedido_uuid}/comprovante")
async def consultar_foto(servidor_id: UUID, pedido_uuid: UUID, db: AsyncSession = Depends(get_db), usuario: Usuario = Depends(GESTAO)):
    pedido = await db.get(PedidoConsolidado, (str(servidor_id), str(pedido_uuid)))
    if pedido is None:
        raise HTTPException(404, "Pedido consolidado não encontrado")
    await verificar_acesso_filial(pedido.filial_id, usuario, db)
    foto = await db.scalar(select(FotoConsolidada).options(undefer(FotoConsolidada.dados))
        .where(FotoConsolidada.servidor_id == str(servidor_id), FotoConsolidada.sha256 == pedido.foto_sha256))
    if foto is None:
        raise HTTPException(404, "O comprovante ainda não foi recebido do servidor local")
    return Response(content=foto.dados, media_type="image/jpeg", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/relatorios/rede/{servidor_id}/pedidos/{pedido_uuid}/historico")
async def consultar_historico(servidor_id: UUID, pedido_uuid: UUID, db: AsyncSession = Depends(get_db), usuario: Usuario = Depends(GESTAO)):
    pedido = await db.get(PedidoConsolidado, (str(servidor_id), str(pedido_uuid)))
    if pedido is None:
        raise HTTPException(404, "Pedido consolidado não encontrado")
    await verificar_acesso_filial(pedido.filial_id, usuario, db)
    return {"historico": pedido.conteudo["historico"], "eventos": pedido.conteudo["eventos"]}
