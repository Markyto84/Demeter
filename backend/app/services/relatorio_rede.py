"""União dos registros do central com os pedidos recebidos dos servidores locais."""
from copy import deepcopy

from sqlalchemy import DateTime, String, case, cast, func, literal, select, union_all

from ..models.models import ComprovanteEntrega, Dieta, EntregaPedido, Filial, Pedido, RecebimentoQR
from ..models.rede import FotoConsolidada, PedidoConsolidado
from .exportacao_dietas import COLUNAS
from .operacao import data_utc
from .relatorio_dietas import ConsultaDietas, agrupar, consulta_base, detalhar

COLUNAS_REDE = [*COLUNAS, ("pedido_uuid", "Identificação global", 40), ("origem_servidor", "Origem do registro", 26),
    ("servidor_id", "Servidor da unidade", 40), ("sincronizado_em", "Recebido no central (UTC)", 28),
    ("comprovante_pendente", "Foto aguardando sincronização", 28)]


def combinar(filiais, inicio, fim, data_base="solicitacao", tipo=None, status=None):
    data_local = func.coalesce(ComprovanteEntrega.entregue_em, RecebimentoQR.confirmado_em, EntregaPedido.entregue_em) if data_base == "entrega" else Pedido.criado_em
    data_remota = cast(PedidoConsolidado.conteudo["detalhe"]["entregue_em"].as_string(), DateTime) if data_base == "entrega" else PedidoConsolidado.criado_em
    categoria = func.coalesce(Dieta.nome, case((Pedido.tipo_solicitacao == "MEDICO", "Refeição médica"), else_="Dieta não informada"))
    local = select(Pedido.uuid_global.label("uuid"), Pedido.id.label("id"), literal("CENTRAL").label("origem"),
        literal(None, type_=String).label("servidor"), Pedido.filial_id.label("filial_id"), Filial.nome.label("unidade"),
        Filial.codigo_slug.label("codigo"), categoria.label("dieta"), Pedido.status.label("status"), Pedido.tipo_solicitacao.label("tipo"),
        Pedido.criado_em.label("criado_em"), data_local.label("data_ref")).join(Filial, Filial.id == Pedido.filial_id).outerjoin(Dieta, Dieta.id == Pedido.dieta_id)
    if data_base == "entrega":
        local = local.outerjoin(ComprovanteEntrega, ComprovanteEntrega.pedido_id == Pedido.id).outerjoin(RecebimentoQR, RecebimentoQR.pedido_id == Pedido.id).outerjoin(EntregaPedido, EntregaPedido.pedido_id == Pedido.id)
    remoto = select(PedidoConsolidado.pedido_uuid, PedidoConsolidado.pedido_local_id, literal("UNIDADE"), PedidoConsolidado.servidor_id,
        PedidoConsolidado.filial_id, Filial.nome, Filial.codigo_slug, PedidoConsolidado.dieta, PedidoConsolidado.status,
        PedidoConsolidado.tipo_solicitacao, PedidoConsolidado.criado_em, data_remota).join(Filial, Filial.id == PedidoConsolidado.filial_id)
    uniao = union_all(local, remoto).subquery("registros_rede")
    filtros = [uniao.c.filial_id.in_(filiais), uniao.c.data_ref >= inicio, uniao.c.data_ref <= fim]
    if tipo:
        filtros.append(uniao.c.tipo == tipo)
    if status:
        filtros.append(uniao.c.status == status)
    return uniao, filtros


async def resumo(db, uniao, filtros):
    linhas = (await db.execute(select(uniao.c.filial_id, uniao.c.codigo, uniao.c.unidade,
        literal(None), uniao.c.dieta, uniao.c.status, func.count()).where(*filtros)
        .group_by(uniao.c.filial_id, uniao.c.codigo, uniao.c.unidade, uniao.c.dieta, uniao.c.status))).all()
    return agrupar(linhas)


async def detalhar_registro(db, registro):
    if registro.origem == "CENTRAL":
        linha = (await db.execute(consulta_base(ConsultaDietas([Pedido.id == registro.id], {})))).one()
        return {**detalhar(linha), "pedido_uuid": registro.uuid, "origem_servidor": "Central", "servidor_id": None,
            "sincronizado_em": None, "comprovante_pendente": False}
    pedido = await db.get(PedidoConsolidado, (registro.servidor, registro.uuid))
    foto = await db.get(FotoConsolidada, (registro.servidor, pedido.foto_sha256)) if pedido.foto_sha256 else None
    dados = deepcopy(pedido.conteudo["detalhe"])
    return {**dados, "unidade_id": registro.filial_id, "unidade": registro.unidade, "unidade_codigo": registro.codigo,
        "pedido_uuid": registro.uuid, "origem_servidor": "Servidor da unidade", "servidor_id": registro.servidor,
        "sincronizado_em": data_utc(pedido.recebido_em), "comprovante_disponivel": foto is not None,
        "comprovante_pendente": bool(pedido.foto_sha256 and foto is None)}


async def listar(db, uniao, filtros, pagina=None):
    consulta = select(uniao).where(*filtros).order_by(uniao.c.criado_em.desc(), uniao.c.uuid, uniao.c.servidor)
    if pagina is not None:
        consulta = consulta.offset((pagina - 1) * 25).limit(25)
    return [await detalhar_registro(db, registro) for registro in (await db.execute(consulta)).all()]
