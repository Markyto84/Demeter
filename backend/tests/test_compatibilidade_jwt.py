"""Compatibilidade com token anterior fictício e rejeição de credenciais incompletas."""
from datetime import datetime
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
import jwt
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base
from app.core.security import get_current_user
from app.models.models import Perfil, SessaoUsuario, Usuario

# Chave e token exclusivamente fictícios, emitidos pela biblioteca anterior.
CHAVE_FICTICIA = 'CHAVE-FICTICIA-COMPATIBILIDADE-JWT-DEMETER-2026'
TOKEN_ANTERIOR_FICTICIO = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwicGVyZmlsIjoiQURNSU5fVEkiLCJub21lIjoiUGVzc29hIGZpY3RpY2lhIiwiZXhwIjoyMjA4OTg4ODAwLCJqdGkiOiJjb21wYXRpYmlsaWRhZGUtdG9rZW4tYW50ZXJpb3IifQ.CQDBKR0QdvXA0XihYFthX1qh-hKDYeWyg7GES23I9hA'


class CompatibilidadeJWTTest(unittest.IsolatedAsyncioTestCase):
    async def test_sessao_anterior_continua_valida_sem_trocar_senha(self):
        motor=create_async_engine("sqlite+aiosqlite:///:memory:")
        sessoes=async_sessionmaker(motor,expire_on_commit=False)
        try:
            async with motor.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with sessoes() as db:
                db.add(Usuario(id=1,nome="Pessoa ficticia",nome_usuario="pessoa",senha_hash="hash-ficticio-preservado",perfil=Perfil(nome="ADMIN_TI")))
                await db.flush()
                db.add(SessaoUsuario(id="compatibilidade-token-anterior",usuario_id=1,expira_em=datetime(2040,1,1)))
                await db.commit()
                with patch.object(settings,"JWT_SECRET",CHAVE_FICTICIA):
                    usuario=await get_current_user(TOKEN_ANTERIOR_FICTICIO,db)
                self.assertEqual(usuario.id,1)
                self.assertEqual(usuario.senha_hash,"hash-ficticio-preservado")
        finally:
            await motor.dispose()

    async def test_claims_obrigatorios_e_algoritmo_sao_conferidos_antes_do_banco(self):
        completo={"sub":"1","exp":2208988800,"jti":"sessao-ficticia"}
        tokens=[jwt.encode({k:v for k,v in completo.items() if k!=ausente},CHAVE_FICTICIA,algorithm="HS256") for ausente in completo]
        tokens.append(jwt.encode(completo,None,algorithm="none"))
        with patch.object(settings,"JWT_SECRET",CHAVE_FICTICIA):
            for token in tokens:
                banco=AsyncMock()
                with self.assertRaises(HTTPException) as erro:
                    await get_current_user(token,banco)
                self.assertEqual(erro.exception.status_code,401)
                banco.execute.assert_not_called()
                banco.get.assert_not_called()
