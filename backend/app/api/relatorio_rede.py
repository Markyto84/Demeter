"""Relatório da rede: permissões por unidade e a mesma visão para tela e arquivos."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import exigir_perfis, filiais_permitidas, verificar_acesso_filial
from ..models.models import Usuario
from ..services.central_unidades import exigir_central
from ..services.exportacao_dietas import exportar_dietas
from ..services.relatorio_dietas import BRASILIA, STATUS, TIPOS
from ..services import relatorio_rede as servico

router = APIRouter(prefix="/api/relatorios/rede", tags=["Relatórios consolidados da rede"])


async def preparar(inicio: datetime, fim: datetime, filial_id: int | None = Query(default=None, gt=0),
    data_base: Literal["solicitacao", "entrega"] = "solicitacao", tipo_solicitacao: Literal["PACIENTE", "MEDICO"] | None = None,
    status: Literal["PENDENTE", "EM_PREPARO", "PRONTO", "ENTREGUE", "CANCELADO"] | None = None,
    db: AsyncSession = Depends(get_db), usuario: Usuario = Depends(exigir_perfis("ADMIN_TI", "NUTRICIONISTA"))):
    exigir_central()
    inicio = inicio.replace(tzinfo=BRASILIA) if inicio.tzinfo is None else inicio
    fim = fim.replace(tzinfo=BRASILIA) if fim.tzinfo is None else fim
    if inicio > fim:
        raise HTTPException(422, "A data e hora inicial devem ser anteriores ou iguais às finais")
    filiais = [await verificar_acesso_filial(filial_id, usuario, db)] if filial_id else await filiais_permitidas(usuario, db)
    uniao, filtros = servico.combinar([f.id for f in filiais], inicio.astimezone(timezone.utc).replace(tzinfo=None),
        fim.astimezone(timezone.utc).replace(tzinfo=None), data_base, tipo_solicitacao, status)
    contexto = {"inicio": inicio.astimezone(BRASILIA).isoformat(), "fim": fim.astimezone(BRASILIA).isoformat(),
        "data_base": data_base, "unidades": [f"{f.nome} ({f.codigo_slug})" for f in filiais],
        "tipo": TIPOS.get(tipo_solicitacao, "Todos"), "status": STATUS.get(status, "Todos")}
    # A autorização já terminou. Abre a visão consistente sem reter uma segunda
    # conexão no pool e sem misturar escritas ao trabalho de relatório.
    await db.rollback()
    if db.bind.dialect.name == "postgresql":
        await db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
    return uniao, filtros, contexto


@router.get("")
async def visualizar(consulta=Depends(preparar), pagina: int = Query(default=1, ge=1), db: AsyncSession = Depends(get_db)):
    uniao, filtros, contexto = consulta
    resumo, totais = await servico.resumo(db, uniao, filtros)
    itens = await servico.listar(db, uniao, filtros, pagina)
    return {"contexto": contexto, "resumo": resumo, "totais": totais, "itens": itens, "pagina": pagina,
        "total_paginas": max(1, (totais["total"] + 24) // 25), "observacao": "Os dados dos servidores locais refletem a última sincronização recebida"}


@router.get("/exportar")
async def exportar(formato: Literal["xlsx", "ods", "csv"], consulta=Depends(preparar), db: AsyncSession = Depends(get_db)):
    uniao, filtros, contexto = consulta
    resumo, totais = await servico.resumo(db, uniao, filtros)
    itens = await servico.listar(db, uniao, filtros)
    try:
        dados, mime = await run_in_threadpool(exportar_dietas, formato, itens, resumo, totais, contexto, servico.COLUNAS_REDE)
    except ValueError as erro:
        raise HTTPException(400, str(erro)) from None
    return Response(content=dados, media_type=mime, headers={"Content-Disposition": f'attachment; filename="demeter-rede.{formato}"',
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
