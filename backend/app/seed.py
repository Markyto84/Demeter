"""Inicialização mínima; demonstração é opcional e exclusiva de desenvolvimento."""
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .core.security import hash_senha
from .core.config import settings
from .core.politica_senha import validar_senha
from .models.models import (
    Dieta,
    Filial,
    FormularioConfig,
    Perfil,
    Usuario,
)
from .api.gestao import ESQUEMA_PADRAO_ENFERMAGEM, ESQUEMA_PADRAO_MEDICO

logger = logging.getLogger(__name__)

DIETAS_DEMO = [
    ("Geral", "Dieta normal / livre", False),
    ("Branda", "Dieta branda, de fácil digestão", False),
    ("Pastosa", "Consistência pastosa", False),
    ("Líquida", "Apenas líquidos", False),
    ("Hipossódica", "Baixo teor de sódio", False),
    ("Enteral", "Nutrição enteral — ATENÇÃO à via", True),
]

async def executar_seed(db: AsyncSession) -> None:
    if settings.APP_ENV == "production" and settings.INICIALIZAR_DEMONSTRACAO:
        raise RuntimeError("Produção não pode receber dados de demonstração")
    # Completa somente perfis ausentes. Não recria administrador em uma instalação
    # que ainda não cadastrou sua primeira unidade e já possui usuários.
    perfis = {p.nome: p for p in (await db.execute(select(Perfil))).scalars().all()}
    for nome in ("ADMIN_TI", "NUTRICIONISTA", "COZINHA", "COPEIRA"):
        if nome not in perfis:
            perfis[nome] = Perfil(nome=nome)
            db.add(perfis[nome])
    total_usuarios = await db.scalar(select(func.count()).select_from(Usuario))
    total_filiais = await db.scalar(select(func.count()).select_from(Filial))
    if total_usuarios or total_filiais:
        await db.commit()
        return

    if not settings.ADMIN_INICIAL_SENHA:
        raise RuntimeError("Base vazia: configure ADMIN_INICIAL_SENHA para criar o administrador inicial")
    validar_senha(settings.ADMIN_INICIAL_SENHA)

    logger.info("Base vazia — criando somente perfis e administrador inicial...")
    await db.flush()

    usuario = Usuario(nome="Administrador TI", nome_usuario="admin", senha_hash=hash_senha(settings.ADMIN_INICIAL_SENHA),
        perfil_id=perfis["ADMIN_TI"].id, troca_senha_obrigatoria=True)
    db.add(usuario)

    if not settings.INICIALIZAR_DEMONSTRACAO:
        await db.commit()
        logger.info("Inicialização concluída: administrador com senha temporária; nenhum dado operacional criado.")
        return

    filial = Filial(nome="Unidade de demonstração", codigo_slug="demonstracao", ip_impressora=None)
    db.add(filial)
    await db.flush()

    dietas = [Dieta(filial_id=filial.id, nome=n, descricao=d, severa=s) for n, d, s in DIETAS_DEMO]
    db.add_all(dietas)

    db.add_all(
        [
            FormularioConfig(filial_id=filial.id, tipo_publico="MEDICO", esquema_json=ESQUEMA_PADRAO_MEDICO),
            FormularioConfig(filial_id=filial.id, tipo_publico="ENFERMAGEM", esquema_json=ESQUEMA_PADRAO_ENFERMAGEM),
        ]
    )

    await db.commit()
    logger.info("Demonstração de desenvolvimento concluída: 1 filial, 1 administrador, %s dietas.", len(dietas))
