"""Estado persistente da sincronização entre unidades e central."""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from .models import JSONType


class ServidorUnidade(Base):
    __tablename__ = "servidores_unidades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filial_id: Mapped[int] = mapped_column(ForeignKey("filiais.id", ondelete="RESTRICT"), unique=True, nullable=False)
    url_local: Mapped[str] = mapped_column(String(300), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    credencial_ativa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    operacao_ativada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    instalacao_uuid: Mapped[str | None] = mapped_column(String(36))
    geracao: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    intervalo_segundos: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    ultimo_contato: Mapped[datetime | None] = mapped_column(DateTime)
    ultima_publicacao: Mapped[datetime | None] = mapped_column(DateTime)
    versao_aplicacao: Mapped[str | None] = mapped_column(String(30))
    pedidos_pendentes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conflitos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    espaco_livre_bytes: Mapped[int | None] = mapped_column(BigInteger)
    espaco_total_bytes: Mapped[int | None] = mapped_column(BigInteger)
    ultimo_erro: Mapped[str | None] = mapped_column(String(300))
    cadastros: Mapped[dict | None] = mapped_column(JSONType)
    cadastros_sha256: Mapped[str | None] = mapped_column(String(64))
    cadastros_em: Mapped[datetime | None] = mapped_column(DateTime)


class EstadoUnidadeLocal(Base):
    __tablename__ = "estado_unidade_local"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    servidor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    instalacao_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    geracao: Mapped[int] = mapped_column(Integer, nullable=False)
    intervalo_segundos: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    filial_id: Mapped[int | None] = mapped_column(ForeignKey("filiais.id", ondelete="RESTRICT"))
    operacao_ativada: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ultimo_contato: Mapped[datetime | None] = mapped_column(DateTime)
    ultima_publicacao: Mapped[datetime | None] = mapped_column(DateTime)
    ultimo_erro: Mapped[str | None] = mapped_column(String(300))
    lease_dono: Mapped[str | None] = mapped_column(String(36))
    lease_ate: Mapped[datetime | None] = mapped_column(DateTime)
    central_instancia: Mapped[str | None] = mapped_column(String(36))
    reconciliacao_cursor: Mapped[str | None] = mapped_column(String(36))
    ultima_reconciliacao: Mapped[datetime | None] = mapped_column(DateTime)


class PublicacaoPedido(Base):
    __tablename__ = "publicacoes_pedidos"
    __table_args__ = (Index("ix_publicacao_pendente", "tentar_apos", "pedido_id"),)

    # Uma inserção por mudança, sem atualizar uma linha compartilhada pelo pedido.
    # Evita adicionar ciclos de locks entre o atendimento e o consumidor de impressão.
    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    pedido_uuid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    pedido_id: Mapped[int] = mapped_column(Integer, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    tentar_apos: Mapped[datetime | None] = mapped_column(DateTime)
    tentativas: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    erro: Mapped[str | None] = mapped_column(String(300))


class TentativaPublicacao(Base):
    __tablename__ = "tentativas_publicacoes"
    __table_args__ = (UniqueConstraint("pedido_uuid", "revisao", name="uq_tentativa_pedido_revisao"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pedido_uuid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    revisao: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class PedidoConsolidado(Base):
    __tablename__ = "pedidos_consolidados"
    __table_args__ = (Index("ix_consolidado_filial_data", "filial_id", "criado_em"),)

    servidor_id: Mapped[str] = mapped_column(ForeignKey("servidores_unidades.id", ondelete="RESTRICT"), primary_key=True)
    pedido_uuid: Mapped[str] = mapped_column(String(36), primary_key=True)
    filial_id: Mapped[int] = mapped_column(ForeignKey("filiais.id", ondelete="RESTRICT"), nullable=False)
    pedido_local_id: Mapped[int] = mapped_column(Integer, nullable=False)
    revisao: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    conteudo: Mapped[dict] = mapped_column(JSONType, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    tipo_solicitacao: Mapped[str] = mapped_column(String(20), nullable=False)
    dieta: Mapped[str] = mapped_column(String(100), nullable=False)
    foto_sha256: Mapped[str | None] = mapped_column(String(64))
    recebido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class VersaoConsolidada(Base):
    __tablename__ = "versoes_consolidadas"

    servidor_id: Mapped[str] = mapped_column(ForeignKey("servidores_unidades.id", ondelete="RESTRICT"), primary_key=True)
    pedido_uuid: Mapped[str] = mapped_column(String(36), primary_key=True)
    revisao: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    anterior_sha256: Mapped[str | None] = mapped_column(String(64))
    conteudo: Mapped[dict] = mapped_column(JSONType, nullable=False)
    recebido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class FotoConsolidada(Base):
    __tablename__ = "fotos_consolidadas"

    servidor_id: Mapped[str] = mapped_column(ForeignKey("servidores_unidades.id", ondelete="RESTRICT"), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), primary_key=True)
    dados: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    largura: Mapped[int] = mapped_column(Integer, nullable=False)
    altura: Mapped[int] = mapped_column(Integer, nullable=False)
    bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    recebido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class AlteracaoCadastroRemota(Base):
    __tablename__ = "alteracoes_cadastros_remotas"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    servidor_id: Mapped[str] = mapped_column(ForeignKey("servidores_unidades.id", ondelete="RESTRICT"), nullable=False, index=True)
    entidade: Mapped[str] = mapped_column(String(100), nullable=False)
    base_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    dados_cifrados: Mapped[str | None] = mapped_column(Text, deferred=True)
    autor_nome: Mapped[str] = mapped_column(String(100), nullable=False)
    autor_perfil: Mapped[str] = mapped_column(String(50), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), default="PENDENTE", nullable=False)
    motivo: Mapped[str] = mapped_column(String(500), nullable=False)
    resultado: Mapped[str | None] = mapped_column(String(300))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime)


class AplicacaoCadastroLocal(Base):
    __tablename__ = "aplicacoes_cadastros_locais"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entidade: Mapped[str] = mapped_column(String(100), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    confirmado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    autor_nome: Mapped[str] = mapped_column(String(100), nullable=False)
    resultado: Mapped[str] = mapped_column(String(300), nullable=False)
    antes: Mapped[dict | None] = mapped_column(JSONType)
    depois: Mapped[dict | None] = mapped_column(JSONType)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
