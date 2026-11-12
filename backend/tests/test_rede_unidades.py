"""Rede com bancos PostgreSQL separados, transporte real ASGI e dados fictícios."""
import asyncio
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx
from PIL import Image
from cryptography.fernet import Fernet
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import undefer

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.migracao_rede import instalar_captura
from app.core.security import hash_senha
from app.main import app
from app.models.models import Dieta, Filial, Pedido, Perfil, Usuario, RecebimentoQR, ComprovanteEntrega, TrabalhoImpressao, AvisoEmailPedido
from app.models.rede import AlteracaoCadastroRemota, AplicacaoCadastroLocal, EstadoUnidadeLocal, FotoConsolidada, PedidoConsolidado, PublicacaoPedido, ServidorUnidade, TentativaPublicacao, VersaoConsolidada
from app.services import central_unidades as central
from app.services.agente_unidade import AgenteUnidade, confirmar_eventos, inicializar_estado, obter_snapshot
from app.services.protocolo_rede import VinculoLocal
from app.services.relatorio_rede import combinar, listar, resumo


@unittest.skipUnless(os.environ.get("DEMETER_TEST_POSTGRES_URL"), "Requer PostgreSQL de teste")
class RedeUnidadesTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.patches = [patch.object(settings, "MODO_SERVIDOR", "CENTRAL"), patch.object(settings, "URL_PUBLICA", "https://central.example.test"),
            patch.object(settings, "EMAIL_CREDENCIAIS_CHAVE", Fernet.generate_key().decode()),
            patch.object(settings, "APP_ENV", "test"), patch.object(settings, "SINCRONIZACAO_VINCULO", Path(tempfile.gettempdir()) / "demeter-teste.json")]
        for p in self.patches: p.start()
        self.admin = create_async_engine(os.environ["DEMETER_TEST_POSTGRES_URL"])
        self.engines, self.fabricas, self.schemas = [], [], []
        for _ in range(3):
            schema = "rede_" + uuid4().hex
            self.schemas.append(schema)
            async with self.admin.begin() as conn:
                await conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            engine = create_async_engine(os.environ["DEMETER_TEST_POSTGRES_URL"], connect_args={"server_settings": {"search_path": schema}})
            self.engines.append(engine)
            self.fabricas.append(async_sessionmaker(engine, expire_on_commit=False))
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                await conn.run_sync(instalar_captura)
        self.central, self.local, self.local2 = self.fabricas
        async def banco():
            async with self.central() as db: yield db
        app.dependency_overrides[get_db] = banco
        self.clients = []
        self.vinculo, self.agente = await self.preparar(self.local, "alfa")

    async def asyncTearDown(self):
        for client in self.clients: await client.aclose()
        app.dependency_overrides.clear()
        for engine in self.engines: await engine.dispose()
        async with self.admin.begin() as conn:
            for schema in self.schemas: await conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        await self.admin.dispose()
        for p in reversed(self.patches): p.stop()

    async def preparar(self, fabrica, slug):
        async with self.central() as db:
            filial = Filial(nome="Unidade fictícia " + slug, codigo_slug=slug)
            db.add(filial)
            await db.flush()
            no, bundle = await central.registrar_servidor(db, filial.id, "https://" + slug + ".example.test", 60)
            await db.commit()
        vinculo = VinculoLocal(**bundle, instalacao_uuid=uuid4())
        await inicializar_estado(fabrica, vinculo)
        cliente = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://central.example.test",
            headers={"Authorization": "Bearer " + vinculo.token.get_secret_value()})
        self.clients.append(cliente)
        agente = AgenteUnidade(fabrica, vinculo, cliente)
        await agente.contato()
        async with self.central() as db:
            await central.ativar_servidor(db, str(vinculo.servidor_id))
            await db.commit()
        await agente.contato()
        return vinculo, agente

    async def pedido(self, fabrica=None, **valores):
        async with (fabrica or self.local)() as db:
            filial = await db.scalar(select(Filial))
            pedido = Pedido(filial_id=filial.id, tipo_solicitacao="PACIENTE", solicitante_identificacao="TESTE", nome_paciente="Pessoa fictícia", **valores)
            db.add(pedido)
            await db.commit()
            return pedido

    async def contar(self, modelo, fabrica=None):
        async with (fabrica or self.central)() as db:
            return await db.scalar(select(func.count()).select_from(modelo))

    async def test_reenvio_e_rollback_nao_perdem_nem_duplicam_efeitos(self):
        async with self.local() as db:
            db.add(Pedido(filial_id=1, tipo_solicitacao="PACIENTE", solicitante_identificacao="TESTE"))
            await db.flush()
            await db.rollback()
        self.assertEqual(await self.contar(PublicacaoPedido, self.local), 0)
        pedido = await self.pedido()
        with patch.object(self.agente, "chamar", side_effect=httpx.ConnectError("offline")):
            with self.assertRaises(httpx.ConnectError): await self.agente.publicar()
        async with self.local() as db:
            await db.execute(update(Pedido).where(Pedido.id == pedido.id).values(status="PRONTO"))
            await db.commit()
        await self.agente.publicar()
        self.assertEqual(await self.contar(PublicacaoPedido, self.local), 0)
        self.assertEqual(await self.contar(PedidoConsolidado), 1)
        for modelo in (Pedido, TrabalhoImpressao, AvisoEmailPedido): self.assertEqual(await self.contar(modelo), 0)
        self.assertEqual(await self.contar(VersaoConsolidada), 1)

    async def test_resposta_perdida_repete_sem_duplicar(self):
        await self.pedido()
        chamar = self.agente.chamar
        async def perder(caminho, dados):
            retorno = await chamar(caminho, dados)
            if caminho == "pedidos": raise httpx.ReadTimeout("resposta perdida")
            return retorno
        with patch.object(self.agente, "chamar", side_effect=perder):
            with self.assertRaises(httpx.ReadTimeout): await self.agente.publicar()
        self.assertGreater(await self.contar(PublicacaoPedido, self.local), 0)
        await self.agente.publicar()
        self.assertEqual(await self.contar(VersaoConsolidada), 1)
        self.assertEqual(await self.contar(PublicacaoPedido, self.local), 0)

    async def test_ack_limpa_somente_eventos_visiveis_no_snapshot(self):
        pedido = await self.pedido()
        async with self.local() as atrasada:
            await atrasada.execute(text("SELECT demeter_marcar_publicacao(:id)"), {"id": pedido.id})
            async with self.local() as posterior:
                await posterior.execute(text("SELECT demeter_marcar_publicacao(:id)"), {"id": pedido.id})
                await posterior.commit()  # ID maior confirma antes da transação atrasada.
            snapshot = await obter_snapshot(self.local, pedido.uuid_global)
            await atrasada.commit()
        async with self.local() as db:
            await confirmar_eventos(db, snapshot)
            await db.commit()
        self.assertEqual(await self.contar(PublicacaoPedido, self.local), 1)
        await self.agente.publicar()
        self.assertEqual(await self.contar(PublicacaoPedido, self.local), 0)

    async def test_duas_unidades_com_id_local_igual_e_relatorio_consolidado(self):
        _, agente2 = await self.preparar(self.local2, "beta")
        p1, p2 = await self.pedido(), await self.pedido(self.local2)
        self.assertEqual((p1.id, p2.id), (1, 1))
        self.assertNotEqual(p1.uuid_global, p2.uuid_global)
        await self.agente.publicar(); await agente2.publicar()
        async with self.central() as db:
            uniao, filtros = combinar([1, 2], central.agora() - timedelta(days=1), central.agora() + timedelta(days=1))
            itens = await listar(db, uniao, filtros)
            _, totais = await resumo(db, uniao, filtros)
            self.assertEqual(totais["total"], 2)
            self.assertEqual(len({i["pedido_uuid"] for i in itens}), 2)
            uniao, filtros = combinar([1], central.agora() - timedelta(days=1), central.agora() + timedelta(days=1))
            self.assertEqual(len(await listar(db, uniao, filtros)), 1)

    async def test_restauracao_central_reconstroi_registro_confirmado(self):
        await self.pedido(); await self.agente.publicar()
        async with self.central() as db:
            await db.execute(delete(VersaoConsolidada)); await db.execute(delete(PedidoConsolidado)); await db.commit()
        await self.agente.reconciliar()
        self.assertEqual(await self.contar(PublicacaoPedido, self.local), 1)
        await self.agente.publicar()
        self.assertEqual(await self.contar(PedidoConsolidado), 1)

    async def test_restauracao_local_desconhecida_nao_sobrescreve_central(self):
        pedido = await self.pedido(); await self.agente.publicar()
        async with self.local() as db:
            await db.execute(delete(TentativaPublicacao))
            db.add(TentativaPublicacao(pedido_uuid=pedido.uuid_global, revisao=50, sha256="0" * 64))
            await db.execute(update(Pedido).where(Pedido.id == pedido.id).values(status="EM_PREPARO")); await db.commit()
        await self.agente.publicar()
        async with self.local() as db:
            fila = await db.scalar(select(PublicacaoPedido))
            self.assertTrue(fila.erro.startswith("DIVERGENCIA:"))
        async with self.central() as db:
            self.assertEqual((await db.scalar(select(PedidoConsolidado))).status, "PENDENTE")

    async def test_central_bloqueia_escrita_e_vinculo_nao_aceita_segunda_instalacao(self):
        async with self.central() as db:
            db.add(Pedido(filial_id=1, tipo_solicitacao="MEDICO", solicitante_identificacao="TESTE"))
            with self.assertRaises(DBAPIError): await db.commit()
        resposta = await self.clients[0].post(f"/api/rede/v1/{self.vinculo.servidor_id}/contato", json={
            "instalacao_uuid": str(uuid4()), "geracao": 1, "versao": "teste"})
        self.assertEqual(resposta.status_code, 409, resposta.text)
        async with self.central() as db:
            no = await db.get(ServidorUnidade, str(self.vinculo.servidor_id)); no.credencial_ativa = False; await db.commit()
        with self.assertRaises(httpx.HTTPStatusError): await self.agente.contato()
        await self.pedido()  # A revogação de sincronização não interrompe atendimento já ativado.

    async def test_foto_pendente_retoma_e_confere_integridade(self):
        pedido = await self.pedido(status="ENTREGUE")
        arquivo = BytesIO(); Image.new("RGB", (700, 1000), "white").save(arquivo, "JPEG")
        dados = arquivo.getvalue(); digest = sha256(dados).hexdigest()
        async with self.local() as db:
            perfil = Perfil(nome="NUTRICIONISTA"); usuario = Usuario(nome="Fictício", nome_usuario="teste", senha_hash="inutilizado", perfil=perfil)
            db.add(usuario); await db.flush()
            db.add(RecebimentoQR(pedido_id=pedido.id, codigo="x" * 43, versao=1, url_base="https://alfa.example.test")); await db.flush()
            db.add(ComprovanteEntrega(pedido_id=pedido.id, entregue_em=central.agora(), registrado_por_usuario_id=usuario.id,
                registrado_por_nome=usuario.nome, foto_jpeg=dados, foto_sha256=digest, foto_bytes=len(dados), foto_largura=700, foto_altura=1000))
            await db.commit()
        await self.agente.publicar()
        async with self.central() as db: refs = await central.fotos_pendentes(db, str(self.vinculo.servidor_id))
        self.assertEqual(len(refs), 1)
        resposta = await self.clients[0].put(f'/api/rede/v1/{self.vinculo.servidor_id}/pedidos/{pedido.uuid_global}/foto/{digest}',
            content=b'foto-corrompida', headers={'X-Demeter-Instalacao': str(self.vinculo.instalacao_uuid), 'X-Demeter-Geracao': '1'})
        self.assertEqual(resposta.status_code, 422)
        self.assertEqual(await self.contar(FotoConsolidada), 0)
        await self.agente.enviar_fotos(refs); await self.agente.enviar_fotos(refs)
        self.assertEqual(await self.contar(FotoConsolidada), 1)
        async with self.central() as db: self.assertEqual(await central.fotos_pendentes(db, str(self.vinculo.servidor_id)), [])

    async def administrador(self):
        async with self.central() as db:
            db.add(Usuario(nome="TI fictícia", nome_usuario="admin_teste", senha_hash=hash_senha("Ficticio@12"), perfil=Perfil(nome="ADMIN_TI")))
            await db.commit()
        resposta = await self.clients[0].post("/api/auth/login", data={"username": "admin_teste", "password": "Ficticio@12"})
        self.assertEqual(resposta.status_code, 200, resposta.text)
        return {"Authorization": "Bearer " + resposta.json()["access_token"]}

    async def propor(self, entidade, dados):
        cabecalho = await self.administrador()
        await self.agente.contato()
        caminho = f"/api/rede/cadastros/{self.vinculo.servidor_id}"
        estado = (await self.clients[0].get(caminho, headers=cabecalho)).json()
        resposta = await self.clients[0].post(caminho, headers=cabecalho, json={"entidade": entidade,
            "base_sha256": estado["bases"][entidade], "dados": dados, "motivo": "Homologação com dados fictícios"})
        self.assertEqual(resposta.status_code, 202, resposta.text)
        return resposta.json()

    async def test_cadastro_da_central_aplica_uma_vez_com_confirmacao(self):
        comando = await self.propor("dieta:nova", {"nome": "GERAL", "descricao": "Exemplo"})
        await self.agente.contato()
        self.assertEqual(await self.contar(Dieta, self.local), 1)
        self.agente.cadastros_enviados = None  # Reinício entre aplicação e envio do recibo.
        await self.agente.contato(); await self.agente.contato()
        self.assertEqual(await self.contar(Dieta, self.local), 1)
        async with self.central() as db:
            atual = await db.scalar(select(AlteracaoCadastroRemota).options(undefer(AlteracaoCadastroRemota.dados_cifrados)).where(AlteracaoCadastroRemota.id == comando["id"]))
            self.assertEqual(atual.estado, "APLICADA")
            self.assertIsNone(atual.dados_cifrados)

    async def test_alteracoes_concorrentes_de_cadastro_preservam_local(self):
        async with self.local() as db:
            db.add(Dieta(filial_id=1, nome="GERAL")); await db.commit()
        comando = await self.propor("dieta:1", {"nome": "GERAL CENTRAL"})
        async with self.local() as db:
            await db.execute(update(Dieta).where(Dieta.id == 1).values(nome="GERAL UNIDADE")); await db.commit()
        await self.agente.contato(); await self.agente.contato()
        async with self.local() as db: self.assertEqual((await db.get(Dieta, 1)).nome, "GERAL UNIDADE")
        async with self.central() as db: self.assertEqual((await db.get(AlteracaoCadastroRemota, comando["id"])).estado, "CONFLITO")

    async def test_credencial_remota_usa_senha_temporaria_sem_replicar_hash(self):
        async with self.local() as db:
            db.add(Perfil(nome="NUTRICIONISTA")); await db.commit()
        comando = await self.propor("usuario:novo", {"nome": "Nutrição fictícia", "nome_usuario": "nutri_teste", "perfil": "NUTRICIONISTA", "senha": "Ficticio@12"})
        await self.agente.contato(); await self.agente.contato()
        async with self.local() as db:
            usuario = await db.scalar(select(Usuario))
            self.assertTrue(usuario.troca_senha_obrigatoria)
            recibo = await db.get(AplicacaoCadastroLocal, comando["id"])
            self.assertNotIn("Ficticio@12", str(recibo.depois))
        async with self.central() as db:
            no = await db.get(ServidorUnidade, str(self.vinculo.servidor_id))
            self.assertNotIn("senha", str(no.cadastros))

    async def test_ativacao_recusa_pedidos_centrais_pendentes_e_preparacao_bloqueia_local(self):
        async with self.local() as db:
            estado = await db.get(EstadoUnidadeLocal, 1); estado.operacao_ativada = False; await db.commit()
        with self.assertRaises(DBAPIError): await self.pedido()
        async with self.central() as db:
            no = await db.get(ServidorUnidade, str(self.vinculo.servidor_id)); no.operacao_ativada = False
            filial = await db.get(Filial, 1); filial.servidor_unidade_id = None; await db.commit()
            db.add(Pedido(filial_id=1, tipo_solicitacao="MEDICO", solicitante_identificacao="TESTE")); await db.commit()
        async with self.central() as db:
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as erro: await central.ativar_servidor(db, str(self.vinculo.servidor_id))
            self.assertEqual(erro.exception.status_code, 409)

    async def test_ativacao_aguarda_envio_concorrente_e_nao_deixa_pedido_sem_responsavel(self):
        async with self.central() as db:
            no = await db.get(ServidorUnidade, str(self.vinculo.servidor_id)); no.operacao_ativada = False
            filial = await db.get(Filial, 1); filial.servidor_unidade_id = None; await db.commit()
        async def ativar():
            from fastapi import HTTPException
            async with self.central() as db:
                try:
                    await central.ativar_servidor(db, str(self.vinculo.servidor_id)); await db.commit()
                    return 200
                except HTTPException as e: return e.status_code
        async with self.central() as solicitacao:
            solicitacao.add(Pedido(filial_id=1, tipo_solicitacao='MEDICO', solicitante_identificacao='TESTE'))
            await solicitacao.flush()
            tarefa = asyncio.create_task(ativar())
            await asyncio.sleep(.1)
            self.assertFalse(tarefa.done(), 'A ativação ignorou o bloqueio do envio em andamento')
            await solicitacao.commit()
            self.assertEqual(await asyncio.wait_for(tarefa, 5), 409)

    async def test_relatorio_e_cadastros_respeitam_vinculo_da_nutricao(self):
        pedido = await self.pedido(); await self.agente.publicar()
        async with self.central() as db:
            outra = Filial(nome='Unidade restrita fictícia', codigo_slug='restrita')
            usuario = Usuario(nome='Nutrição fictícia', nome_usuario='nutri_teste', senha_hash=hash_senha('Ficticio@12'),
                perfil=Perfil(nome='NUTRICIONISTA'), filiais=[outra])
            db.add(usuario); await db.commit()
        token = (await self.clients[0].post('/api/auth/login', data={'username':'nutri_teste','password':'Ficticio@12'})).json()['access_token']
        cabecalho={'Authorization':'Bearer '+token}
        params={'inicio':'2020-01-01T00:00:00Z','fim':'2030-01-01T00:00:00Z'}
        resposta=await self.clients[0].get('/api/relatorios/rede', params=params, headers=cabecalho)
        self.assertEqual(resposta.status_code, 200, resposta.text)
        self.assertEqual(resposta.json()['totais']['total'], 0)
        for caminho in (f'/api/rede/cadastros/{self.vinculo.servidor_id}',
            f'/api/relatorios/rede/{self.vinculo.servidor_id}/pedidos/{pedido.uuid_global}/comprovante'):
            self.assertEqual((await self.clients[0].get(caminho, headers=cabecalho)).status_code, 403)


if __name__ == "__main__": unittest.main()
