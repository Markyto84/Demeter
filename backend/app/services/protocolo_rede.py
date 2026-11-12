"""Contrato sem credenciais de usuários, comandos de impressão ou códigos de recebimento."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

PROTOCOLO = 1
MAX_LOTE_BYTES = 2 * 1024 * 1024
MAX_ITENS_LOTE = 20


def canonico(valor):
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def resumo_sha(valor):
    return sha256(canonico(valor)).hexdigest()


def horario(valor):
    data = datetime.fromisoformat(valor.replace("Z", "+00:00")) if isinstance(valor, str) else valor
    if not isinstance(data, datetime) or data.tzinfo is None:
        raise ValueError("Horário deve conter fuso")
    return data.astimezone(timezone.utc).replace(tzinfo=None)


class VinculoLocal(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    protocolo: Literal[1] = 1
    servidor_id: UUID
    central_url: str = Field(max_length=300)
    token: SecretStr
    instalacao_uuid: UUID
    geracao: int = Field(ge=1)
    intervalo_segundos: int = Field(default=60, ge=15, le=3600)

    @field_validator("token")
    @classmethod
    def token_forte(cls, valor):
        if not 40 <= len(valor.get_secret_value()) <= 200:
            raise ValueError("Credencial de vínculo inválida")
        return valor


class ContatoUnidade(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocolo: Literal[1] = 1
    instalacao_uuid: UUID
    geracao: int = Field(ge=1)
    versao: str = Field(min_length=1, max_length=30)
    pedidos_pendentes: int = Field(default=0, ge=0)
    conflitos: int = Field(default=0, ge=0)
    espaco_livre_bytes: int | None = Field(default=None, ge=0)
    espaco_total_bytes: int | None = Field(default=None, ge=0)
    configurada: bool = False
    cadastros_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    cadastros: dict | None = None
    resultados_cadastros: list[dict] = Field(default_factory=list, max_length=20)


class FotoReferencia(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(gt=0, le=300 * 1024)
    largura: int = Field(ge=1, le=2000)
    altura: int = Field(ge=1, le=2000)


class RegistroPedido(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pedido_uuid: UUID
    pedido_local_id: int = Field(gt=0)
    revisao: int = Field(gt=0)
    anterior_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    conteudo: dict


class LotePedidos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    protocolo: Literal[1] = 1
    instalacao_uuid: UUID
    geracao: int = Field(ge=1)
    registros: list[RegistroPedido] = Field(min_length=1, max_length=MAX_ITENS_LOTE)
