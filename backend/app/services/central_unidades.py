"""Registro dos servidores e consolidação sem executar efeitos operacionais no central."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import hmac
from io import BytesIO
import secrets
from uuid import uuid4

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import undefer

from ..core.config import settings
from ..models.models import ConfiguracaoOperacional, Dieta, Filial, FormularioConfig, ImpressoraEtiqueta, Pedido, TrabalhoImpressao, AvisoEmailPedido
from ..models.rede import AlteracaoCadastroRemota, FotoConsolidada, PedidoConsolidado, ServidorUnidade, VersaoConsolidada
from .cadastros_rede import comandos_pendentes
from .exportacao_dietas import COLUNAS
from .protocolo_rede import FotoReferencia, RegistroPedido, horario, resumo_sha


def agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def exigir_central():
    if settings.MODO_SERVIDOR != "CENTRAL":
        raise HTTPException(409, "Esta função está disponível no servidor central")


def credencial_hash(token):
    return sha256(token.encode("utf-8")).hexdigest()


def dados_servidor(no):
    campos = {k: getattr(no, k) for k in ("id", "filial_id", "url_local", "credencial_ativa", "operacao_ativada",
        "geracao", "intervalo_segundos", "criado_em", "ultimo_contato", "ultima_publicacao", "versao_aplicacao",
        "pedidos_pendentes", "conflitos", "espaco_livre_bytes", "espaco_total_bytes", "ultimo_erro")}
    return {k: v.replace(tzinfo=timezone.utc).isoformat() if isinstance(v, datetime) else v for k, v in campos.items()}


async def registrar_servidor(db, filial_id, url_local, intervalo):
    exigir_central()
    if not settings.URL_PUBLICA or not settings.URL_PUBLICA.startswith("https://"):
        raise HTTPException(409, "Configure o endereço HTTPS do central antes de emitir o vínculo da unidade")
    filial = await db.scalar(select(Filial).where(Filial.id == filial_id).with_for_update())
    if not filial or not filial.ativa:
        raise HTTPException(404, "Unidade ativa não encontrada")
    if await db.scalar(select(ServidorUnidade.id).where(ServidorUnidade.filial_id == filial_id)):
        raise HTTPException(409, "A unidade já possui um servidor cadastrado")
    token = secrets.token_urlsafe(48)
    no = ServidorUnidade(id=str(uuid4()), filial_id=filial_id, url_local=url_local,
        token_hash=credencial_hash(token), intervalo_segundos=intervalo)
    db.add(no)
    await db.flush()
    return no, vinculo(no, token)


def vinculo(no, token):
    return {"protocolo": 1, "servidor_id": no.id, "central_url": settings.URL_PUBLICA,
        "token": token, "geracao": no.geracao, "intervalo_segundos": no.intervalo_segundos}


async def autenticar_servidor(db, servidor_id, token):
    exigir_central()
    no = await db.scalar(select(ServidorUnidade).where(ServidorUnidade.id == servidor_id).with_for_update())
    if not no or not no.credencial_ativa or not hmac.compare_digest(no.token_hash, credencial_hash(token)):
        raise HTTPException(401, "Credencial de unidade inválida ou revogada")
    return no


def conferir_instalacao(no, instalacao_uuid, geracao, *, publicar=False):
    if no.geracao != geracao or no.instalacao_uuid != str(instalacao_uuid):
        raise HTTPException(409, "Vínculo de outra instalação ou geração; solicite revisão à TI")
    if publicar and not no.operacao_ativada:
        raise HTTPException(409, "A operação local ainda não foi ativada no central")


async def ativar_servidor(db, servidor_id):
    exigir_central()
    no = await db.get(ServidorUnidade, servidor_id)
    if not no:
        raise HTTPException(404, "Servidor não encontrado")
    filial = await db.scalar(select(Filial).where(Filial.id == no.filial_id).with_for_update())
    no = await db.scalar(select(ServidorUnidade).where(ServidorUnidade.id == servidor_id).with_for_update().execution_options(populate_existing=True))
    if no.operacao_ativada:
        return no
    if not no.credencial_ativa or not no.instalacao_uuid:
        raise HTTPException(409, "Prepare e conecte o servidor local antes de ativar")
    if not filial.ativa or filial.servidor_unidade_id:
        raise HTTPException(409, "A unidade está inativa ou já foi vinculada a outra operação")
    pendentes = await db.scalar(select(func.count()).select_from(Pedido).where(Pedido.filial_id == filial.id,
        Pedido.status.in_(("PENDENTE", "EM_PREPARO", "PRONTO"))))
    impressoes = await db.scalar(select(func.count()).select_from(TrabalhoImpressao).join(Pedido, Pedido.id == TrabalhoImpressao.pedido_id).where(Pedido.filial_id == filial.id,
        TrabalhoImpressao.estado.in_(("PENDENTE", "PROCESSANDO"))))
    emails = await db.scalar(select(func.count()).select_from(AvisoEmailPedido).join(Pedido, Pedido.id == AvisoEmailPedido.pedido_id).where(Pedido.filial_id == filial.id,
        AvisoEmailPedido.estado.in_(("PENDENTE", "PROCESSANDO"))))
    if pendentes or impressoes or emails:
        raise HTTPException(409, "Finalize os pedidos e as filas em andamento no central antes de ativar o servidor local")
    no.operacao_ativada = True
    filial.servidor_unidade_id = no.id
    filial.url_servidor_local = no.url_local
    return no


async def configurar_unidade(db, no):
    filial = await db.get(Filial, no.filial_id)
    dietas = (await db.scalars(select(Dieta).where(Dieta.filial_id == no.filial_id).order_by(Dieta.id))).all()
    formularios = (await db.scalars(select(FormularioConfig).where(FormularioConfig.filial_id == no.filial_id))).all()
    prazos = await db.get(ConfiguracaoOperacional, no.filial_id)
    impressora = await db.get(ImpressoraEtiqueta, no.filial_id)
    return {"filial": {"nome": filial.nome, "codigo_slug": filial.codigo_slug, "ip_impressora": filial.ip_impressora},
        "dietas": [{k: getattr(d, k) for k in ("nome", "descricao", "severa", "ativa")} for d in dietas],
        "formularios": [{"tipo_publico": f.tipo_publico, "esquema_json": deepcopy(f.esquema_json)} for f in formularios],
        "prazos": {"preparo_minutos": prazos.preparo_minutos, "entrega_minutos": prazos.entrega_minutos} if prazos else None,
        "impressora_etiquetas": {k: getattr(impressora, k) for k in ("modelo", "ip", "porta", "protocolo", "resolucao", "intervalo_mm")} if impressora else None}


async def receber_contato(db, no, contato):
    no = await db.scalar(select(ServidorUnidade).where(ServidorUnidade.id == no.id).with_for_update())
    if no.geracao != contato.geracao:
        raise HTTPException(409, "Geração do vínculo desatualizada")
    if no.instalacao_uuid is None:
        no.instalacao_uuid = str(contato.instalacao_uuid)
    conferir_instalacao(no, contato.instalacao_uuid, contato.geracao)
    no.ultimo_contato = agora()
    no.versao_aplicacao = contato.versao
    no.pedidos_pendentes = contato.pedidos_pendentes
    no.conflitos = contato.conflitos
    no.espaco_livre_bytes = contato.espaco_livre_bytes
    no.espaco_total_bytes = contato.espaco_total_bytes
    no.ultimo_erro = None
    if contato.cadastros is not None:
        if resumo_sha(contato.cadastros) != contato.cadastros_sha256:
            raise HTTPException(422, "Integridade dos cadastros inválida")
        # A projeção administrativa é uma lista explícita, sem senhas ou chaves.
        for entidade, valor in contato.cadastros.items():
            if not isinstance(entidade, str) or not entidade.startswith(("dieta:", "formulario:", "usuario:")) and entidade not in ("prazos", "impressora", "etiquetas"):
                raise HTTPException(422, "Cadastro não reconhecido")
            if entidade.startswith("usuario:") and valor and set(valor) - {"nome", "nome_usuario", "perfil", "origem_autenticacao", "usuario_ad", "ativo"}:
                raise HTTPException(422, "A projeção de credenciais contém campos não permitidos")
        no.cadastros, no.cadastros_sha256, no.cadastros_em = deepcopy(contato.cadastros), contato.cadastros_sha256, agora()
    confirmados = []
    for resultado in contato.resultados_cadastros:
        if resultado.get("estado") not in ("APLICADA", "CONFLITO"):
            raise HTTPException(422, "Resultado administrativo inválido")
        comando = await db.get(AlteracaoCadastroRemota, str(resultado.get("id")))
        if comando and comando.servidor_id == no.id:
            if comando.estado == "PENDENTE":
                comando.estado, comando.resultado = resultado["estado"], str(resultado.get("resultado") or "")[:300]
                comando.concluido_em, comando.dados_cifrados = agora(), None
            elif comando.estado != resultado["estado"]:
                raise HTTPException(409, "Recibo administrativo diverge do resultado já confirmado")
            confirmados.append(comando.id)
    await db.flush()
    return {"protocolo": 1, "operacao_ativada": no.operacao_ativada, "intervalo_segundos": no.intervalo_segundos,
        "configuracao_inicial": await configurar_unidade(db, no) if not contato.configurada else None,
        "fotos_pendentes": await fotos_pendentes(db, no.id), "comandos_cadastros": await comandos_pendentes(db, no.id),
        "confirmados_cadastros": confirmados, "solicitar_cadastros": no.cadastros_sha256 != contato.cadastros_sha256}


async def fotos_pendentes(db, servidor_id):
    linhas = (await db.execute(select(PedidoConsolidado.pedido_uuid, PedidoConsolidado.foto_sha256)
        .outerjoin(FotoConsolidada, (FotoConsolidada.servidor_id == PedidoConsolidado.servidor_id) & (FotoConsolidada.sha256 == PedidoConsolidado.foto_sha256))
        .where(PedidoConsolidado.servidor_id == servidor_id, PedidoConsolidado.foto_sha256.is_not(None), FotoConsolidada.sha256.is_(None))
        .order_by(PedidoConsolidado.recebido_em).limit(10))).all()
    return [{"pedido_uuid": pid, "sha256": digest} for pid, digest in linhas]


def validar_conteudo(registro: RegistroPedido):
    conteudo = registro.conteudo
    try:
        integro = set(conteudo) == {"detalhe", "historico", "eventos", "foto"} and resumo_sha(conteudo) == registro.sha256
    except (ValueError, TypeError, RecursionError):
        integro = False
    if not integro:
        raise HTTPException(422, "Conteúdo de publicação ou integridade inválidos")
    detalhe = conteudo["detalhe"]
    permitidas = {c[0] for c in COLUNAS}
    if not isinstance(detalhe, dict) or set(detalhe) - permitidas:
        raise HTTPException(422, "Campos de relatório não reconhecidos")
    if detalhe.get("pedido_id") != registro.pedido_local_id or detalhe.get("status") not in ("PENDENTE", "EM_PREPARO", "PRONTO", "ENTREGUE", "CANCELADO"):
        raise HTTPException(422, "Identificação ou etapa do pedido inválida")
    if detalhe.get("tipo_solicitacao") not in ("MEDICO", "PACIENTE"):
        raise HTTPException(422, "Tipo de solicitação inválido")
    try:
        criado_em = horario(detalhe["criado_em"])
        for chave in ("entregue_em", "concluido_em", "cancelado_em", "registrado_em", "retirada_em", "prescricao_data_hora", "conferencia_em"):
            if detalhe.get(chave) is not None:
                horario(detalhe[chave])
        foto = FotoReferencia.model_validate(conteudo["foto"]) if conteudo["foto"] else None
    except (ValueError, TypeError, KeyError):
        raise HTTPException(422, "Data ou referência de comprovante inválida") from None
    if not isinstance(conteudo["historico"], list) or not isinstance(conteudo["eventos"], list):
        raise HTTPException(422, "Histórico inválido")
    return detalhe, criado_em, foto


async def receber_lote(db, no, lote):
    no = await db.scalar(select(ServidorUnidade).where(ServidorUnidade.id == no.id).with_for_update().execution_options(populate_existing=True))
    conferir_instalacao(no, lote.instalacao_uuid, lote.geracao, publicar=True)
    resultados = []
    for registro in lote.registros:
        detalhe, criado_em, foto = validar_conteudo(registro)
        pid = str(registro.pedido_uuid)
        atual = await db.get(PedidoConsolidado, (no.id, pid))
        if atual and atual.revisao == registro.revisao and hmac.compare_digest(atual.sha256, registro.sha256):
            resultados.append({"pedido_uuid": pid, "revisao": registro.revisao, "sha256": registro.sha256})
            continue
        if atual and (registro.revisao <= atual.revisao or registro.anterior_sha256 != atual.sha256):
            raise HTTPException(409, "Divergência de publicação; os dados recebidos anteriormente foram preservados")
        if atual is None and registro.anterior_sha256 is not None:
            raise HTTPException(409, "O central não possui o antecedente informado; confira a recuperação do banco")
        if atual is None:
            atual = PedidoConsolidado(servidor_id=no.id, pedido_uuid=pid, filial_id=no.filial_id)
            db.add(atual)
        atual.pedido_local_id, atual.revisao, atual.sha256 = registro.pedido_local_id, registro.revisao, registro.sha256
        atual.conteudo, atual.criado_em = deepcopy(registro.conteudo), criado_em
        atual.status, atual.tipo_solicitacao = detalhe["status"], detalhe["tipo_solicitacao"]
        atual.dieta = str(detalhe.get("dieta") or "Dieta não informada")[:100]
        atual.foto_sha256, atual.recebido_em = foto.sha256 if foto else None, agora()
        db.add(VersaoConsolidada(servidor_id=no.id, pedido_uuid=pid, revisao=registro.revisao, sha256=registro.sha256,
            anterior_sha256=registro.anterior_sha256, conteudo=deepcopy(registro.conteudo)))
        resultados.append({"pedido_uuid": pid, "revisao": registro.revisao, "sha256": registro.sha256})
        await db.flush()
    no.ultima_publicacao = agora()
    return {"confirmados": resultados, "fotos_pendentes": await fotos_pendentes(db, no.id)}


async def receber_foto(db, no, pedido_uuid, digest, dados):
    no = await db.scalar(select(ServidorUnidade).where(ServidorUnidade.id == no.id).with_for_update())
    pedido = await db.get(PedidoConsolidado, (no.id, str(pedido_uuid)))
    if not pedido or pedido.foto_sha256 != digest:
        raise HTTPException(409, "O comprovante não pertence à versão atual do pedido desta unidade")
    if not 0 < len(dados) <= 300 * 1024 or sha256(dados).hexdigest() != digest:
        raise HTTPException(422, "Tamanho ou integridade do comprovante inválido")
    ref = FotoReferencia.model_validate(pedido.conteudo["foto"])
    try:
        with Image.open(BytesIO(dados)) as imagem:
            if imagem.format != "JPEG" or imagem.size != (ref.largura, ref.altura) or max(imagem.size) > 2000 or imagem.info.get("exif"):
                raise ValueError()
            imagem.verify()
    except (ValueError, OSError, UnidentifiedImageError):
        raise HTTPException(422, "A imagem não corresponde ao comprovante informado") from None
    if len(dados) != ref.bytes:
        raise HTTPException(422, "O tamanho do comprovante divergiu")
    if await db.get(FotoConsolidada, (no.id, digest)) is None:
        db.add(FotoConsolidada(servidor_id=no.id, sha256=digest, dados=dados, largura=ref.largura, altura=ref.altura, bytes=len(dados)))
    return {"sha256": digest, "recebido": True}
