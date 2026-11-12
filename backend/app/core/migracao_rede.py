"""Identidades globais e fila transacional capturada pelo PostgreSQL."""
from uuid import uuid4

from sqlalchemy import inspect, text


def preparar_identidades(conn):
    insp = inspect(conn)
    if insp.has_table("filiais"):
        colunas = {c["name"] for c in insp.get_columns("filiais")}
        for nome, tamanho in (("servidor_unidade_id", 36), ("url_servidor_local", 300)):
            if nome not in colunas:
                conn.execute(text(f"ALTER TABLE filiais ADD COLUMN {nome} VARCHAR({tamanho})"))
    if not insp.has_table("pedidos"):
        return
    if "uuid_global" not in {c["name"] for c in insp.get_columns("pedidos")}:
        conn.execute(text("ALTER TABLE pedidos ADD COLUMN uuid_global VARCHAR(36)"))
    if conn.dialect.name == "postgresql":
        conn.execute(text("UPDATE pedidos SET uuid_global = gen_random_uuid()::text WHERE uuid_global IS NULL"))
        conn.execute(text("ALTER TABLE pedidos ALTER COLUMN uuid_global SET NOT NULL"))
        conn.execute(text("ALTER TABLE pedidos ALTER COLUMN uuid_global SET DEFAULT (gen_random_uuid()::text)"))
    else:
        for pedido_id in conn.execute(text("SELECT id FROM pedidos WHERE uuid_global IS NULL")).scalars():
            conn.execute(text("UPDATE pedidos SET uuid_global=:uuid WHERE id=:id"), {"uuid": str(uuid4()), "id": pedido_id})
    unicos = [c["column_names"] for c in inspect(conn).get_unique_constraints("pedidos")]
    unicos += [c["column_names"] for c in inspect(conn).get_indexes("pedidos") if c.get("unique")]
    if ["uuid_global"] not in unicos:
        conn.execute(text("CREATE UNIQUE INDEX uq_pedido_uuid_global ON pedidos (uuid_global)"))


FUNCOES = r"""
CREATE OR REPLACE FUNCTION demeter_validar_filial_operacao(fid integer) RETURNS void AS $$
DECLARE proprietario text; local_ativo boolean; local_filial integer;
BEGIN
    SELECT servidor_unidade_id INTO proprietario FROM filiais WHERE id=fid FOR SHARE;
    IF proprietario IS NOT NULL THEN
        RAISE EXCEPTION 'DEMETER_SERVIDOR_LOCAL: unidade opera no servidor local' USING ERRCODE='P0001';
    END IF;
    SELECT operacao_ativada, filial_id INTO local_ativo, local_filial FROM estado_unidade_local WHERE id=1;
    IF FOUND AND (NOT local_ativo OR local_filial IS DISTINCT FROM fid) THEN
        RAISE EXCEPTION 'DEMETER_UNIDADE_EM_PREPARACAO: servidor local ainda nao ativado ou unidade incorreta' USING ERRCODE='P0001';
    END IF;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION demeter_validar_pedido_operacao() RETURNS trigger AS $$
DECLARE fid integer; pid integer;
BEGIN
    IF TG_TABLE_NAME='pedidos' THEN
        IF TG_OP='DELETE' THEN
            IF EXISTS(SELECT 1 FROM estado_unidade_local WHERE id=1) THEN
                RAISE EXCEPTION 'DEMETER_PEDIDO_PRESERVADO: use cancelamento; nao apague um pedido local';
            END IF;
            fid := OLD.filial_id;
        ELSE
            fid := NEW.filial_id;
            IF TG_OP='UPDATE' AND NEW.uuid_global IS DISTINCT FROM OLD.uuid_global THEN
                RAISE EXCEPTION 'DEMETER_IDENTIDADE_IMUTAVEL: identidade do pedido nao pode mudar';
            END IF;
        END IF;
    ELSE
        IF TG_OP='DELETE' THEN pid := OLD.pedido_id; ELSE pid := NEW.pedido_id; END IF;
        SELECT filial_id INTO fid FROM pedidos WHERE id=pid;
    END IF;
    IF fid IS NOT NULL THEN PERFORM demeter_validar_filial_operacao(fid); END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION demeter_marcar_publicacao(pid integer) RETURNS void AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM estado_unidade_local WHERE id=1) THEN RETURN; END IF;
    INSERT INTO publicacoes_pedidos(pedido_uuid,pedido_id,criado_em,tentativas)
        SELECT uuid_global,id,clock_timestamp(),0 FROM pedidos WHERE id=pid;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION demeter_capturar_pedido() RETURNS trigger AS $$
DECLARE pid integer;
BEGIN
    IF TG_TABLE_NAME='pedidos' THEN
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        pid := NEW.id;
    ELSE
        IF TG_OP='DELETE' THEN pid := OLD.pedido_id; ELSE pid := NEW.pedido_id; END IF;
    END IF;
    PERFORM demeter_marcar_publicacao(pid);
    IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION demeter_dieta_alterada() RETURNS trigger AS $$
DECLARE pid integer;
BEGIN
    IF EXISTS(SELECT 1 FROM estado_unidade_local WHERE id=1) THEN
        FOR pid IN SELECT id FROM pedidos WHERE dieta_id=NEW.id LOOP
            PERFORM demeter_marcar_publicacao(pid);
        END LOOP;
    END IF;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION demeter_unica_filial_local() RETURNS trigger AS $$
DECLARE fid integer;
BEGIN
    SELECT filial_id INTO fid FROM estado_unidade_local WHERE id=1;
    IF fid IS NOT NULL AND NEW.id IS DISTINCT FROM fid THEN
        RAISE EXCEPTION 'DEMETER_UNIDADE_UNICA: um servidor local atende somente uma unidade';
    END IF;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION demeter_cadastro_da_unidade() RETURNS trigger AS $$
DECLARE fid integer; proprietario text;
BEGIN
    IF TG_OP='DELETE' THEN fid := OLD.filial_id; ELSE fid := NEW.filial_id; END IF;
    SELECT servidor_unidade_id INTO proprietario FROM filiais WHERE id=fid FOR SHARE;
    IF proprietario IS NOT NULL THEN
        RAISE EXCEPTION 'DEMETER_SERVIDOR_LOCAL: cadastro administrado no servidor da unidade';
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END; $$ LANGUAGE plpgsql;
"""

TABELAS = ("pedidos", "historico_pedidos", "eventos_assistenciais", "recebimentos_qr", "comprovantes_entrega",
    "retiradas_pedidos", "entregas_pedidos", "recebimentos_entregas", "trabalhos_impressao")


def instalar_captura(conn):
    preparar_identidades(conn)
    if conn.dialect.name != "postgresql":
        return
    for funcao in FUNCOES.split("$$ LANGUAGE plpgsql;"):
        if funcao.strip():
            conn.exec_driver_sql(funcao + "$$ LANGUAGE plpgsql;")
    for tabela in TABELAS:
        for tipo, funcao, quando in (("validar", "demeter_validar_pedido_operacao", "BEFORE"),
                ("capturar", "demeter_capturar_pedido", "AFTER")):
            nome = f"demeter_{tipo}_{tabela}"
            conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {nome} ON {tabela}")
            conn.exec_driver_sql(f"CREATE TRIGGER {nome} {quando} INSERT OR UPDATE OR DELETE ON {tabela} FOR EACH ROW EXECUTE FUNCTION {funcao}()")
    for nome, tabela, eventos, funcao in (
        ("demeter_capturar_dieta", "dietas", "UPDATE OF nome", "demeter_dieta_alterada"),
        ("demeter_filial_local", "filiais", "INSERT", "demeter_unica_filial_local"),
    ):
        conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {nome} ON {tabela}")
        conn.exec_driver_sql(f"CREATE TRIGGER {nome} AFTER {eventos} ON {tabela} FOR EACH ROW EXECUTE FUNCTION {funcao}()")
    for tabela in ("dietas", "formularios_config", "configuracoes_operacionais", "impressoras_etiquetas"):
        nome = f"demeter_cadastro_{tabela}"
        conn.exec_driver_sql(f"DROP TRIGGER IF EXISTS {nome} ON {tabela}")
        conn.exec_driver_sql(f"CREATE TRIGGER {nome} BEFORE INSERT OR UPDATE OR DELETE ON {tabela} FOR EACH ROW EXECUTE FUNCTION demeter_cadastro_da_unidade()")
