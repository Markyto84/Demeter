"""Inicialização de produção em banco isolado; nenhuma limpeza de banco existente."""
import unittest
from unittest.mock import patch

import httpx
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings, settings
from app.core.database import Base, get_db
from app.core.security import hash_senha, verificar_senha
from app.main import app
from app.models.models import Dieta, Filial, FormularioConfig, Perfil, Usuario
from app.seed import executar_seed


class BancoLimpoTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.motor = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessoes = async_sessionmaker(self.motor, expire_on_commit=False)
        async with self.motor.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        for chave, valor in (("APP_ENV", "production"), ("INICIALIZAR_DEMONSTRACAO", False),
            ("ADMIN_INICIAL_SENHA", "Inicial@123"), ("JWT_SECRET", "SEGREDO-FICTICIO-BANCO-LIMPO-" * 3)):
            modificacao = patch.object(settings, chave, valor)
            modificacao.start()
            self.addCleanup(modificacao.stop)
        async def banco():
            async with self.sessoes() as db:
                yield db
        app.dependency_overrides[get_db] = banco
        self.cliente = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://teste")

    async def asyncTearDown(self):
        await self.cliente.aclose()
        app.dependency_overrides.clear()
        await self.motor.dispose()

    async def test_producao_cria_somente_quatro_perfis_e_admin_temporario(self):
        async with self.sessoes() as db:
            await executar_seed(db)
            for nome, tabela in Base.metadata.tables.items():
                total = await db.scalar(select(func.count()).select_from(tabela))
                self.assertEqual(total, 4 if nome == "perfis" else 1 if nome == "usuarios" else 0, nome)
            admin = await db.scalar(select(Usuario))
            self.assertEqual(admin.nome_usuario, "admin")
            self.assertTrue(admin.troca_senha_obrigatoria)
            self.assertTrue(verificar_senha("Inicial@123", admin.senha_hash))

    async def test_reiniciar_sem_unidades_nao_recria_admin_nem_altera_senha(self):
        async with self.sessoes() as db:
            await executar_seed(db)
            admin = await db.scalar(select(Usuario))
            admin.senha_hash = hash_senha("Escolhi@123")
            admin.troca_senha_obrigatoria = False
            admin.ativo = False
            await db.commit()
            senha_anterior = admin.senha_hash
        for _ in range(2):
            async with self.sessoes() as db:
                await executar_seed(db)
                admin = await db.scalar(select(Usuario))
                self.assertEqual(await db.scalar(select(func.count()).select_from(Usuario)), 1)
                self.assertEqual(admin.senha_hash, senha_anterior)
                self.assertFalse(admin.ativo)
                self.assertFalse(admin.troca_senha_obrigatoria)
                self.assertEqual(await db.scalar(select(func.count()).select_from(Filial)), 0)

    async def test_base_existente_e_preservada(self):
        async with self.sessoes() as db:
            filial = Filial(nome="Unidade fictícia existente", codigo_slug="existente")
            db.add(filial)
            await db.flush()
            db.add(Dieta(nome="Cadastro fictício existente", filial_id=filial.id))
            await db.commit()
            await executar_seed(db)
            self.assertEqual(await db.scalar(select(func.count()).select_from(Usuario)), 0)
            self.assertEqual(await db.scalar(select(func.count()).select_from(Filial)), 1)
            self.assertEqual(await db.scalar(select(func.count()).select_from(Dieta)), 1)

    async def test_primeiro_login_e_primeira_unidade_funcionam_sem_demo(self):
        async with self.sessoes() as db:
            await executar_seed(db)
        login = await self.cliente.post("/api/auth/login", data={"username": "admin", "password": "Inicial@123"})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["filiais"], [])
        cabecalho = {"Authorization": "Bearer " + login.json()["access_token"]}
        self.assertEqual((await self.cliente.get("/api/admin/filiais", headers=cabecalho)).status_code, 403)
        troca = await self.cliente.post("/api/auth/senha", headers=cabecalho, json={"senha_atual": "Inicial@123", "nova_senha": "Escolhi@123"})
        self.assertEqual(troca.status_code, 200)
        cabecalho = {"Authorization": "Bearer " + troca.json()["access_token"]}
        unidades = await self.cliente.get("/api/admin/filiais", headers=cabecalho)
        self.assertEqual(unidades.json(), [])
        criada = await self.cliente.post("/api/admin/filiais", headers=cabecalho, json={"nome": "Primeira unidade fictícia", "codigo_slug": "primeira-unidade"})
        self.assertEqual(criada.status_code, 201)
        async with self.sessoes() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(FormularioConfig)), 2)
            self.assertEqual(await db.scalar(select(func.count()).select_from(Dieta)), 0)
            await executar_seed(db)
            self.assertEqual(await db.scalar(select(func.count()).select_from(Usuario)), 1)
            self.assertEqual(await db.scalar(select(func.count()).select_from(Filial)), 1)

    async def test_demonstração_exige_opcao_explicita_e_nunca_producao(self):
        with patch.object(settings, "INICIALIZAR_DEMONSTRACAO", True):
            async with self.sessoes() as db:
                with self.assertRaises(RuntimeError):
                    await executar_seed(db)
            with patch.object(settings, "APP_ENV", "development"):
                async with self.sessoes() as db:
                    await executar_seed(db)
                    self.assertEqual(await db.scalar(select(func.count()).select_from(Filial)), 1)
                    self.assertGreater(await db.scalar(select(func.count()).select_from(Dieta)), 0)


class ConfiguracaoLimpaTest(unittest.TestCase):
    def test_producao_rejeita_demo_e_padrao_nao_habilita_exemplos(self):
        argumentos = {"_env_file": None, "JWT_SECRET": "SEGREDO-FICTICIO-VALIDACAO-" * 3,
            "DATABASE_URL": "postgresql+asyncpg://dietas:credencial-ficticia-longa@db/dietas", "APP_ENV": "production"}
        self.assertFalse(Settings(**argumentos).INICIALIZAR_DEMONSTRACAO)
        with self.assertRaises(ValidationError):
            Settings(**argumentos, INICIALIZAR_DEMONSTRACAO=True)
