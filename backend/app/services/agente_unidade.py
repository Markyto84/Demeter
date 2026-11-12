"""Sincronização fora do fluxo clínico: persistência local, retomada e confirmação explícita."""
import asyncio
from copy import deepcopy
from datetime import timedelta
import json
import random
import shutil
import ssl
from uuid import uuid4

import httpx
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from ..core.config import settings
from ..core.versao import VERSAO
from ..models.models import ComprovanteEntrega, ConfiguracaoOperacional, Dieta, EventoAssistencial, Filial, FormularioConfig, HistoricoPedido, ImpressoraEtiqueta, Pedido, Usuario
from ..models.rede import AplicacaoCadastroLocal, EstadoUnidadeLocal, PublicacaoPedido, TentativaPublicacao
from . import cadastros_rede
from fastapi import HTTPException
from pydantic import ValidationError
from .central_unidades import agora
from .operacao import data_utc
from .protocolo_rede import MAX_ITENS_LOTE, MAX_LOTE_BYTES, VinculoLocal, canonico, resumo_sha
from .relatorio_dietas import ConsultaDietas, consulta_base, detalhar
from ..core.endereco_publico import normalizar_endereco_publico


class DivergenciaUnidade(Exception):
    pass


def carregar_vinculo():
    try:
        vinculo = VinculoLocal.model_validate_json(settings.SINCRONIZACAO_VINCULO.read_text(encoding="utf-8"))
        endereco = normalizar_endereco_publico(vinculo.central_url)
        if not endereco.startswith("https://") and settings.APP_ENV != "test":
            raise ValueError()
        vinculo.central_url = endereco
        return vinculo
    except (OSError, ValueError, AttributeError):
        raise RuntimeError("Vínculo privado inválido ou central sem HTTPS. Confira a configuração da unidade") from None


async def inicializar_estado(sessoes, vinculo):
    async with sessoes() as db:
        if db.bind.dialect.name != "postgresql":
            raise RuntimeError("O servidor local requer PostgreSQL")
        estado = await db.get(EstadoUnidadeLocal, 1)
        if estado is None:
            if await db.scalar(select(func.count()).select_from(Filial)):
                raise RuntimeError("Configure uma instalação nova e vazia para vincular o servidor local")
            db.add(EstadoUnidadeLocal(id=1, servidor_id=str(vinculo.servidor_id), instalacao_uuid=str(vinculo.instalacao_uuid), geracao=vinculo.geracao))
        elif estado.servidor_id != str(vinculo.servidor_id) or estado.instalacao_uuid != str(vinculo.instalacao_uuid):
            raise RuntimeError("A identidade do vínculo diverge deste banco. Não reutilize uma cópia em dois servidores")
        elif estado.geracao != vinculo.geracao:
            estado.geracao = vinculo.geracao
        await db.commit()


async def importar_configuracao(db, estado, config):
    if estado.filial_id is not None:
        return
    if not config or await db.scalar(select(func.count()).select_from(Filial)):
        raise DivergenciaUnidade("A preparação da unidade precisa de uma base nova e configuração válida")
    filial = Filial(**config["filial"])
    db.add(filial)
    await db.flush()
    estado.filial_id = filial.id
    for dieta in config["dietas"]:
        db.add(Dieta(filial_id=filial.id, **dieta))
    for formulario in config["formularios"]:
        db.add(FormularioConfig(filial_id=filial.id, **formulario))
    if config.get("prazos"):
        db.add(ConfiguracaoOperacional(filial_id=filial.id, **config["prazos"]))
    if config.get("impressora_etiquetas"):
        db.add(ImpressoraEtiqueta(filial_id=filial.id, **config["impressora_etiquetas"]))


async def pendencias(db):
    total = await db.scalar(select(func.count(func.distinct(PublicacaoPedido.pedido_uuid))))
    conflitos = await db.scalar(select(func.count(func.distinct(PublicacaoPedido.pedido_uuid))).where(PublicacaoPedido.erro.like("DIVERGENCIA:%")))
    return total or 0, conflitos or 0


async def obter_snapshot(sessoes, pedido_uuid):
    # O número da revisão é do publicador, não da ordem de alocação de sequences
    # clínicas. Assim, transações que confirmam fora de ordem não perdem eventos.
    engine = sessoes.kw["bind"]
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="REPEATABLE READ")
        async with AsyncSession(bind=conn, expire_on_commit=False) as db:
            eventos_fila = (await db.scalars(select(PublicacaoPedido.id).where(PublicacaoPedido.pedido_uuid == pedido_uuid))).all()
            pedido = await db.scalar(select(Pedido).where(Pedido.uuid_global == pedido_uuid))
            if not eventos_fila or pedido is None:
                return None
            linha = (await db.execute(consulta_base(ConsultaDietas([Pedido.id == pedido.id], {})))).one()
            historico = (await db.execute(select(HistoricoPedido, Usuario.nome).outerjoin(Usuario, Usuario.id == HistoricoPedido.alterado_por_usuario_id)
                .where(HistoricoPedido.pedido_id == pedido.id).order_by(HistoricoPedido.id))).all()
            eventos = (await db.scalars(select(EventoAssistencial).where(EventoAssistencial.pedido_id == pedido.id).order_by(EventoAssistencial.id))).all()
            comprovante = await db.get(ComprovanteEntrega, pedido.id)
            conteudo = {"detalhe": detalhar(linha), "historico": [{"status_anterior": h.status_anterior, "status_novo": h.status_novo,
                "autor_nome": nome, "data_hora": data_utc(h.data_hora)} for h, nome in historico],
                "eventos": [{**{k: getattr(e, k) for k in ("acao", "autor_nome", "autor_perfil", "motivo", "antes", "depois")},
                    "criado_em": data_utc(e.criado_em)} for e in eventos],
                "foto": {"sha256": comprovante.foto_sha256, "bytes": comprovante.foto_bytes, "largura": comprovante.foto_largura,
                    "altura": comprovante.foto_altura} if comprovante else None}
            return {"pedido_uuid": pedido_uuid, "pedido_local_id": pedido.id, "conteudo": conteudo, "sha256": resumo_sha(conteudo), "eventos_fila": list(eventos_fila)}


async def registrar_tentativa(db, snapshot, minimo=0):
    ultima = await db.scalar(select(TentativaPublicacao).where(TentativaPublicacao.pedido_uuid == snapshot["pedido_uuid"])
        .order_by(TentativaPublicacao.revisao.desc()).limit(1))
    if ultima and ultima.sha256 == snapshot["sha256"] and ultima.revisao >= minimo:
        return ultima.revisao
    revisao = max(ultima.revisao if ultima else 0, minimo) + 1
    db.add(TentativaPublicacao(pedido_uuid=snapshot["pedido_uuid"], revisao=revisao, sha256=snapshot["sha256"]))
    await db.flush()
    return revisao


async def confirmar_eventos(db, snapshot):
    await db.execute(delete(PublicacaoPedido).where(PublicacaoPedido.id.in_(snapshot["eventos_fila"])))


async def adiar(db, snapshot, motivo, segundos=60):
    await db.execute(update(PublicacaoPedido).where(PublicacaoPedido.id.in_(snapshot["eventos_fila"]))
        .values(erro=motivo[:300], tentar_apos=agora() + timedelta(seconds=segundos), tentativas=PublicacaoPedido.tentativas + 1))


class AgenteUnidade:
    def __init__(self, sessoes, vinculo, cliente):
        self.sessoes, self.vinculo, self.cliente = sessoes, vinculo, cliente
        self.dono = str(uuid4())
        self.cadastros_enviados = None

    async def chamar(self, caminho, dados):
        resposta = await self.cliente.post(f"/api/rede/v1/{self.vinculo.servidor_id}/{caminho}", json=dados)
        resposta.raise_for_status()
        return resposta.json()

    async def adquirir(self):
        async with self.sessoes() as db:
            atual = await db.scalar(update(EstadoUnidadeLocal).where(EstadoUnidadeLocal.id == 1,
                or_(EstadoUnidadeLocal.lease_ate.is_(None), EstadoUnidadeLocal.lease_ate < agora(), EstadoUnidadeLocal.lease_dono == self.dono))
                .values(lease_dono=self.dono, lease_ate=agora() + timedelta(minutes=3)).returning(EstadoUnidadeLocal.id))
            await db.commit()
            return atual is not None

    async def contato(self):
        async with self.sessoes() as db:
            estado = await db.get(EstadoUnidadeLocal, 1)
            total, conflitos = await pendencias(db)
            espaco = shutil.disk_usage(settings.SINCRONIZACAO_VINCULO.parent)
            configurada = estado.filial_id is not None
            cadastros = await cadastros_rede.capturar(db, estado.filial_id) if configurada else None
            cadastros_hash = resumo_sha(cadastros) if cadastros is not None else None
            recibos = (await db.scalars(select(AplicacaoCadastroLocal).where(AplicacaoCadastroLocal.confirmado.is_(False)).limit(20))).all()
            resultados = [{"id": r.id, "estado": r.estado, "resultado": r.resultado} for r in recibos]
        contato = await self.chamar("contato", {"protocolo": 1, "instalacao_uuid": str(self.vinculo.instalacao_uuid), "geracao": self.vinculo.geracao,
            "versao": VERSAO, "pedidos_pendentes": total, "conflitos": conflitos, "configurada": configurada,
            "espaco_livre_bytes": espaco.free, "espaco_total_bytes": espaco.total,
            "cadastros_sha256": cadastros_hash, "cadastros": cadastros if cadastros_hash != self.cadastros_enviados else None,
            "resultados_cadastros": resultados})
        self.cadastros_enviados = None if contato.get("solicitar_cadastros") else cadastros_hash
        async with self.sessoes() as db:
            estado = await db.get(EstadoUnidadeLocal, 1)
            await importar_configuracao(db, estado, contato.get("configuracao_inicial"))
            # A perda do vínculo não devolve a escrita ao central nem paralisa a
            # unidade. Uma ativação recebida e persistida continua válida offline.
            if contato["operacao_ativada"]:
                estado.operacao_ativada = True
            estado.ultimo_contato, estado.ultimo_erro = agora(), None
            estado.intervalo_segundos = contato["intervalo_segundos"]
            instancia = contato.get("central_instancia")
            if instancia and estado.central_instancia != instancia:
                estado.central_instancia = instancia
                estado.ultima_reconciliacao, estado.reconciliacao_cursor = None, None
            if contato.get("confirmados_cadastros"):
                await db.execute(update(AplicacaoCadastroLocal).where(AplicacaoCadastroLocal.id.in_(contato["confirmados_cadastros"])).values(confirmado=True))
            await db.commit()
            ativada, filial_id = estado.operacao_ativada, estado.filial_id
        for comando in contato.get("comandos_cadastros", []):
            async with self.sessoes() as db:
                try:
                    await cadastros_rede.aplicar(db, filial_id, comando)
                    await db.commit()
                except (HTTPException, ValidationError):
                    await db.rollback()
                    if not await db.get(AplicacaoCadastroLocal, comando["id"]):
                        db.add(AplicacaoCadastroLocal(id=comando["id"], entidade=comando["entidade"], autor_nome=comando["autor_nome"],
                            estado="CONFLITO", resultado="Cadastro não aplicado. Revise as permissões, estrutura ou dados na unidade"))
                        await db.commit()
            self.cadastros_enviados = None
        return contato, ativada

    async def cursores(self, ids):
        retorno = await self.chamar("estado-publicacoes", {"instalacao_uuid": str(self.vinculo.instalacao_uuid),
            "geracao": self.vinculo.geracao, "pedidos": ids})
        return retorno["pedidos"]

    async def publicar(self):
        async with self.sessoes() as db:
            ids = (await db.execute(select(PublicacaoPedido.pedido_uuid, func.min(PublicacaoPedido.id)).where(
                or_(PublicacaoPedido.tentar_apos.is_(None), PublicacaoPedido.tentar_apos <= agora()))
                .group_by(PublicacaoPedido.pedido_uuid).order_by(func.min(PublicacaoPedido.id)).limit(MAX_ITENS_LOTE))).all()
        if not ids:
            return False
        snapshots = [s for uid, _ in ids if (s := await obter_snapshot(self.sessoes, uid))]
        cursores = await self.cursores([s["pedido_uuid"] for s in snapshots])
        lote, incluidos = [], []
        for snapshot in snapshots:
            cursor = cursores.get(snapshot["pedido_uuid"])
            async with self.sessoes() as db:
                if cursor and cursor["sha256"] != snapshot["sha256"]:
                    conhecido = await db.scalar(select(TentativaPublicacao.id).where(TentativaPublicacao.pedido_uuid == snapshot["pedido_uuid"],
                        TentativaPublicacao.sha256 == cursor["sha256"]).limit(1))
                    if conhecido is None:
                        await adiar(db, snapshot, "DIVERGENCIA: o central possui estado ausente neste banco; confira restauração ou cópia de servidor", 300)
                        await db.commit()
                        continue
                revisao = await registrar_tentativa(db, snapshot, cursor["revisao"] if cursor else 0)
                if cursor and cursor["sha256"] == snapshot["sha256"]:
                    await confirmar_eventos(db, snapshot)
                    await db.commit()
                    continue
                registro = {k: snapshot[k] for k in ("pedido_uuid", "pedido_local_id", "sha256", "conteudo")}
                registro.update(revisao=revisao, anterior_sha256=cursor["sha256"] if cursor else None)
                if len(canonico(registro)) > MAX_LOTE_BYTES - 1024:
                    await adiar(db, snapshot, "Registro excede o limite do lote. Os dados foram mantidos; solicite análise à TI", 300)
                    await db.commit()
                    continue
                await db.commit()  # O hash tentado deve sobreviver à perda da resposta.
            if lote and len(canonico(lote + [registro])) > MAX_LOTE_BYTES - 1024:
                break
            lote.append(registro)
            incluidos.append(snapshot)
        if not lote:
            return False
        retorno = await self.chamar("pedidos", {"protocolo": 1, "instalacao_uuid": str(self.vinculo.instalacao_uuid),
            "geracao": self.vinculo.geracao, "registros": lote})
        confirmados = {(r["pedido_uuid"], r["revisao"], r["sha256"]) for r in retorno.get("confirmados", [])}
        async with self.sessoes() as db:
            for snapshot, registro in zip(incluidos, lote):
                if (registro["pedido_uuid"], registro["revisao"], registro["sha256"]) in confirmados:
                    await confirmar_eventos(db, snapshot)
            estado = await db.get(EstadoUnidadeLocal, 1)
            estado.ultima_publicacao = agora()
            await db.commit()
        return True

    async def enviar_fotos(self, referencias):
        for ref in referencias[:5]:
            async with self.sessoes() as db:
                pedido_id = await db.scalar(select(Pedido.id).where(Pedido.uuid_global == ref["pedido_uuid"]))
                foto = await db.scalar(select(ComprovanteEntrega).options(undefer(ComprovanteEntrega.foto_jpeg))
                    .where(ComprovanteEntrega.pedido_id == pedido_id, ComprovanteEntrega.foto_sha256 == ref["sha256"]))
                if foto is None:
                    if pedido_id and not await db.scalar(select(PublicacaoPedido.id).where(PublicacaoPedido.pedido_uuid == ref["pedido_uuid"]).limit(1)):
                        db.add(PublicacaoPedido(pedido_uuid=ref["pedido_uuid"], pedido_id=pedido_id))
                        await db.commit()
                    continue
                dados = foto.foto_jpeg
            resposta = await self.cliente.put(f"/api/rede/v1/{self.vinculo.servidor_id}/pedidos/{ref['pedido_uuid']}/foto/{ref['sha256']}",
                content=dados, headers={"Content-Type": "image/jpeg", "X-Demeter-Instalacao": str(self.vinculo.instalacao_uuid),
                    "X-Demeter-Geracao": str(self.vinculo.geracao)})
            if resposta.status_code != 409:
                resposta.raise_for_status()

    async def reconciliar(self):
        async with self.sessoes() as db:
            estado = await db.get(EstadoUnidadeLocal, 1)
            if estado.ultima_reconciliacao and estado.ultima_reconciliacao > agora() - timedelta(hours=24):
                return False
            consulta = select(Pedido.uuid_global, Pedido.id).order_by(Pedido.uuid_global).limit(200)
            if estado.reconciliacao_cursor:
                consulta = consulta.where(Pedido.uuid_global > estado.reconciliacao_cursor)
            pagina = (await db.execute(consulta)).all()
        cursores = await self.cursores([uid for uid, _ in pagina]) if pagina else {}
        async with self.sessoes() as db:
            for uid, pedido_id in pagina:
                tentativa = await db.scalar(select(TentativaPublicacao).where(TentativaPublicacao.pedido_uuid == uid)
                    .order_by(TentativaPublicacao.revisao.desc()).limit(1))
                cursor = cursores.get(uid)
                if not cursor or not tentativa or cursor["sha256"] != tentativa.sha256:
                    if not await db.scalar(select(PublicacaoPedido.id).where(PublicacaoPedido.pedido_uuid == uid).limit(1)):
                        db.add(PublicacaoPedido(pedido_uuid=uid, pedido_id=pedido_id))
            estado = await db.get(EstadoUnidadeLocal, 1)
            estado.reconciliacao_cursor = pagina[-1][0] if len(pagina) == 200 else None
            estado.ultima_reconciliacao = agora() if len(pagina) < 200 else None
            await db.commit()
        return len(pagina) == 200

    async def executar_uma_vez(self):
        if not await self.adquirir():
            return 30
        contato, ativada = await self.contato()
        if not ativada:
            return contato["intervalo_segundos"]
        if not await self.adquirir():
            return 30
        publicou = await self.publicar()
        if not await self.adquirir():
            return 30
        await self.enviar_fotos(contato.get("fotos_pendentes", []))
        if not await self.adquirir():
            return 30
        reconciliando = await self.reconciliar()
        return 1 if publicou or reconciliando else contato["intervalo_segundos"]


async def executar_agente(sessoes, parar):
    if settings.MODO_SERVIDOR != "UNIDADE":
        return
    vinculo = carregar_vinculo()
    await inicializar_estado(sessoes, vinculo)
    falhas = 0
    cliente = None
    try:
        while not parar.is_set():
            try:
                if cliente is None:
                    contexto_ssl = ssl.create_default_context(cafile=str(settings.SINCRONIZACAO_CA)) if settings.SINCRONIZACAO_CA else ssl.create_default_context()
                    cliente = httpx.AsyncClient(base_url=vinculo.central_url, headers={"Authorization": "Bearer " + vinculo.token.get_secret_value()},
                        verify=contexto_ssl, follow_redirects=False, trust_env=False, timeout=httpx.Timeout(20, connect=5))
                    agente = AgenteUnidade(sessoes, vinculo, cliente)
                esperar = await agente.executar_uma_vez()
                falhas = 0
            except asyncio.CancelledError:
                raise
            except Exception as erro:
                falhas += 1
                if isinstance(erro, httpx.HTTPStatusError):
                    mensagem = f"Central recusou a sincronização (HTTP {erro.response.status_code}). Confira vínculo e versão; dados locais preservados"
                elif isinstance(erro, DivergenciaUnidade):
                    mensagem = str(erro)
                elif isinstance(erro, ssl.SSLError):
                    mensagem = "Certificado do central inválido. Confira a CA; dados locais preservados"
                else:
                    mensagem = "Servidor central indisponível. Operação local mantida; envio será retomado automaticamente"
                async with sessoes() as db:
                    estado = await db.get(EstadoUnidadeLocal, 1)
                    estado.ultimo_erro = mensagem[:300]
                    await db.commit()
                esperar = min(300, 5 * 2 ** min(falhas, 6))
            try:
                await asyncio.wait_for(parar.wait(), timeout=esperar + random.uniform(0, 2))
            except TimeoutError:
                pass
    finally:
        if cliente is not None:
            await cliente.aclose()
            async with sessoes() as db:
                await db.execute(update(EstadoUnidadeLocal).where(EstadoUnidadeLocal.id == 1, EstadoUnidadeLocal.lease_dono == agente.dono)
                    .values(lease_dono=None, lease_ate=None))
                await db.commit()
