--
-- PostgreSQL database dump
--

\restrict WN2HGhjMbhNYw0bCT8e2apAUKSD7YugTrJa8TGhtWlvANgfCBdRecGvUGKaKjQj

-- Dumped from database version 16.15
-- Dumped by pg_dump version 16.15

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA IF NOT EXISTS public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: demeter_cadastro_da_unidade(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.demeter_cadastro_da_unidade() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE fid integer; proprietario text;
BEGIN
    IF TG_OP='DELETE' THEN fid := OLD.filial_id; ELSE fid := NEW.filial_id; END IF;
    SELECT servidor_unidade_id INTO proprietario FROM filiais WHERE id=fid FOR SHARE;
    IF proprietario IS NOT NULL THEN
        RAISE EXCEPTION 'DEMETER_SERVIDOR_LOCAL: cadastro administrado no servidor da unidade';
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END; $$;


--
-- Name: demeter_capturar_pedido(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.demeter_capturar_pedido() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
END; $$;


--
-- Name: demeter_dieta_alterada(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.demeter_dieta_alterada() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE pid integer;
BEGIN
    IF EXISTS(SELECT 1 FROM estado_unidade_local WHERE id=1) THEN
        FOR pid IN SELECT id FROM pedidos WHERE dieta_id=NEW.id LOOP
            PERFORM demeter_marcar_publicacao(pid);
        END LOOP;
    END IF;
    RETURN NEW;
END; $$;


--
-- Name: demeter_marcar_publicacao(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.demeter_marcar_publicacao(pid integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NOT EXISTS(SELECT 1 FROM estado_unidade_local WHERE id=1) THEN RETURN; END IF;
    INSERT INTO publicacoes_pedidos(pedido_uuid,pedido_id,criado_em,tentativas)
        SELECT uuid_global,id,clock_timestamp(),0 FROM pedidos WHERE id=pid;
END; $$;


--
-- Name: demeter_unica_filial_local(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.demeter_unica_filial_local() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE fid integer;
BEGIN
    SELECT filial_id INTO fid FROM estado_unidade_local WHERE id=1;
    IF fid IS NOT NULL AND NEW.id IS DISTINCT FROM fid THEN
        RAISE EXCEPTION 'DEMETER_UNIDADE_UNICA: um servidor local atende somente uma unidade';
    END IF;
    RETURN NEW;
END; $$;


--
-- Name: demeter_validar_filial_operacao(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.demeter_validar_filial_operacao(fid integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
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
END; $$;


--
-- Name: demeter_validar_pedido_operacao(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.demeter_validar_pedido_operacao() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
END; $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alteracoes_cadastros_remotas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alteracoes_cadastros_remotas (
    id character varying(36) NOT NULL,
    servidor_id character varying(36) NOT NULL,
    entidade character varying(100) NOT NULL,
    base_sha256 character varying(64) NOT NULL,
    dados_cifrados text,
    autor_nome character varying(100) NOT NULL,
    autor_perfil character varying(50) NOT NULL,
    estado character varying(20) NOT NULL,
    motivo character varying(500) NOT NULL,
    resultado character varying(300),
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    concluido_em timestamp without time zone
);


--
-- Name: aplicacoes_cadastros_locais; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.aplicacoes_cadastros_locais (
    id character varying(36) NOT NULL,
    entidade character varying(100) NOT NULL,
    estado character varying(20) NOT NULL,
    confirmado boolean NOT NULL,
    autor_nome character varying(100) NOT NULL,
    resultado character varying(300) NOT NULL,
    antes jsonb,
    depois jsonb,
    criado_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: auditoria_administrativa; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auditoria_administrativa (
    id integer NOT NULL,
    autor_usuario_id integer NOT NULL,
    autor_nome character varying(100) NOT NULL,
    filial_id integer,
    entidade character varying(30) NOT NULL,
    entidade_id integer NOT NULL,
    acao character varying(30) NOT NULL,
    antes jsonb,
    depois jsonb,
    criado_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: auditoria_administrativa_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auditoria_administrativa_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auditoria_administrativa_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auditoria_administrativa_id_seq OWNED BY public.auditoria_administrativa.id;


--
-- Name: avisos_email_pedidos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.avisos_email_pedidos (
    id integer NOT NULL,
    pedido_id integer NOT NULL,
    filial_id integer NOT NULL,
    versao integer NOT NULL,
    destinatario character varying(254) NOT NULL,
    resumo jsonb NOT NULL,
    mensagem_id character varying(100) NOT NULL,
    estado character varying(24) NOT NULL,
    tentativas integer NOT NULL,
    erro character varying(250),
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    expira_em timestamp without time zone NOT NULL,
    proxima_tentativa_em timestamp without time zone NOT NULL,
    iniciado_em timestamp without time zone,
    enviado_em timestamp without time zone,
    reserva character varying(36)
);


--
-- Name: avisos_email_pedidos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.avisos_email_pedidos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: avisos_email_pedidos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.avisos_email_pedidos_id_seq OWNED BY public.avisos_email_pedidos.id;


--
-- Name: comprovantes_entrega; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comprovantes_entrega (
    pedido_id integer NOT NULL,
    entregue_em timestamp without time zone NOT NULL,
    registrado_em timestamp without time zone DEFAULT now() NOT NULL,
    registrado_por_usuario_id integer NOT NULL,
    registrado_por_nome character varying(100) NOT NULL,
    foto_jpeg bytea NOT NULL,
    foto_sha256 character varying(64) NOT NULL,
    foto_bytes integer NOT NULL,
    foto_largura integer NOT NULL,
    foto_altura integer NOT NULL
);


--
-- Name: configuracoes_email_unidades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.configuracoes_email_unidades (
    filial_id integer NOT NULL,
    modo character varying(20) NOT NULL,
    remetente character varying(254) NOT NULL,
    senha_cifrada text,
    servidor character varying(253),
    porta integer,
    seguranca character varying(12),
    autenticar boolean,
    usuario character varying(254),
    servidor_secundario character varying(253),
    porta_secundaria integer,
    tempo_limite integer,
    endereco_resposta character varying(254),
    habilitado boolean NOT NULL,
    atualizado_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: configuracoes_operacionais; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.configuracoes_operacionais (
    filial_id integer NOT NULL,
    preparo_minutos integer,
    entrega_minutos integer
);


--
-- Name: contatos_email_pedidos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contatos_email_pedidos (
    pedido_id integer NOT NULL,
    email character varying(254) NOT NULL
);


--
-- Name: dietas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dietas (
    id integer NOT NULL,
    filial_id integer NOT NULL,
    nome character varying(100) NOT NULL,
    descricao text,
    severa boolean NOT NULL,
    ativa boolean NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: COLUMN dietas.severa; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.dietas.severa IS 'Dieta/restrição severa → destaque vermelho no Kanban';


--
-- Name: dietas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.dietas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: dietas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.dietas_id_seq OWNED BY public.dietas.id;


--
-- Name: entregas_pedidos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entregas_pedidos (
    pedido_id integer NOT NULL,
    copeira_id integer NOT NULL,
    copeira_nome character varying(100) NOT NULL,
    registrado_por_usuario_id integer,
    entregue_em timestamp without time zone DEFAULT now() NOT NULL,
    ip_origem character varying(45)
);


--
-- Name: estado_unidade_local; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.estado_unidade_local (
    id integer NOT NULL,
    servidor_id character varying(36) NOT NULL,
    instalacao_uuid character varying(36) NOT NULL,
    geracao integer NOT NULL,
    intervalo_segundos integer NOT NULL,
    filial_id integer,
    operacao_ativada boolean NOT NULL,
    ultimo_contato timestamp without time zone,
    ultima_publicacao timestamp without time zone,
    ultimo_erro character varying(300),
    lease_dono character varying(36),
    lease_ate timestamp without time zone,
    central_instancia character varying(36),
    reconciliacao_cursor character varying(36),
    ultima_reconciliacao timestamp without time zone
);


--
-- Name: estado_unidade_local_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.estado_unidade_local_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: estado_unidade_local_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.estado_unidade_local_id_seq OWNED BY public.estado_unidade_local.id;


--
-- Name: eventos_assistenciais; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.eventos_assistenciais (
    id integer NOT NULL,
    pedido_id integer NOT NULL,
    acao character varying(30) NOT NULL,
    autor_usuario_id integer,
    autor_nome character varying(100),
    autor_perfil character varying(30),
    motivo character varying(1000),
    antes jsonb,
    depois jsonb,
    criado_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: eventos_assistenciais_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.eventos_assistenciais_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: eventos_assistenciais_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.eventos_assistenciais_id_seq OWNED BY public.eventos_assistenciais.id;


--
-- Name: filiais; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.filiais (
    id integer NOT NULL,
    nome character varying(100) NOT NULL,
    codigo_slug character varying(50) NOT NULL,
    ip_impressora character varying(45),
    ativa boolean NOT NULL,
    servidor_unidade_id character varying(36),
    url_servidor_local character varying(300),
    criado_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: filiais_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.filiais_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: filiais_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.filiais_id_seq OWNED BY public.filiais.id;


--
-- Name: formularios_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.formularios_config (
    id integer NOT NULL,
    filial_id integer NOT NULL,
    tipo_publico character varying(20) NOT NULL,
    esquema_json jsonb NOT NULL,
    atualizado_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: formularios_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.formularios_config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: formularios_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.formularios_config_id_seq OWNED BY public.formularios_config.id;


--
-- Name: fotos_consolidadas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fotos_consolidadas (
    servidor_id character varying(36) NOT NULL,
    sha256 character varying(64) NOT NULL,
    dados bytea NOT NULL,
    largura integer NOT NULL,
    altura integer NOT NULL,
    bytes integer NOT NULL,
    recebido_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: historico_pedidos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.historico_pedidos (
    id integer NOT NULL,
    pedido_id integer NOT NULL,
    status_anterior character varying(20),
    status_novo character varying(20) NOT NULL,
    alterado_por_usuario_id integer,
    impresso boolean NOT NULL,
    data_hora timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: historico_pedidos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.historico_pedidos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: historico_pedidos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.historico_pedidos_id_seq OWNED BY public.historico_pedidos.id;


--
-- Name: impressoras_etiquetas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.impressoras_etiquetas (
    filial_id integer NOT NULL,
    modelo character varying(100) NOT NULL,
    ip character varying(45),
    porta integer NOT NULL,
    protocolo character varying(8) NOT NULL,
    resolucao integer NOT NULL,
    intervalo_mm integer NOT NULL
);


--
-- Name: limites_login; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.limites_login (
    chave character varying(64) NOT NULL,
    falhas integer NOT NULL,
    janela_inicio timestamp without time zone NOT NULL
);


--
-- Name: pedidos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pedidos (
    id integer NOT NULL,
    uuid_global character varying(36) DEFAULT (gen_random_uuid())::text NOT NULL,
    filial_id integer NOT NULL,
    tipo_solicitacao character varying(20) NOT NULL,
    solicitante_identificacao character varying(50) NOT NULL,
    solicitante_nome character varying(100),
    leito character varying(30),
    prontuario character varying(50),
    nome_paciente character varying(100),
    dieta_id integer,
    observacoes_alergias text,
    dados_dinamicos jsonb NOT NULL,
    status character varying(20) NOT NULL,
    ip_origem character varying(45),
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    concluido_em timestamp without time zone,
    chave_envio character varying(36),
    hash_envio character varying(64),
    prescricao jsonb,
    versao integer DEFAULT 1 NOT NULL
);


--
-- Name: pedidos_consolidados; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pedidos_consolidados (
    servidor_id character varying(36) NOT NULL,
    pedido_uuid character varying(36) NOT NULL,
    filial_id integer NOT NULL,
    pedido_local_id integer NOT NULL,
    revisao bigint NOT NULL,
    sha256 character varying(64) NOT NULL,
    conteudo jsonb NOT NULL,
    criado_em timestamp without time zone NOT NULL,
    status character varying(20) NOT NULL,
    tipo_solicitacao character varying(20) NOT NULL,
    dieta character varying(100) NOT NULL,
    foto_sha256 character varying(64),
    recebido_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: pedidos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pedidos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pedidos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pedidos_id_seq OWNED BY public.pedidos.id;


--
-- Name: perfis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.perfis (
    id integer NOT NULL,
    nome character varying(50) NOT NULL
);


--
-- Name: perfis_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.perfis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: perfis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.perfis_id_seq OWNED BY public.perfis.id;


--
-- Name: publicacoes_pedidos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.publicacoes_pedidos (
    id bigint NOT NULL,
    pedido_uuid character varying(36) NOT NULL,
    pedido_id integer NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    tentar_apos timestamp without time zone,
    tentativas integer NOT NULL,
    erro character varying(300)
);


--
-- Name: publicacoes_pedidos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.publicacoes_pedidos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: publicacoes_pedidos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.publicacoes_pedidos_id_seq OWNED BY public.publicacoes_pedidos.id;


--
-- Name: recebimentos_entregas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recebimentos_entregas (
    pedido_id integer NOT NULL,
    recebedor_nome character varying(120) NOT NULL,
    assinatura_png bytea NOT NULL
);


--
-- Name: recebimentos_qr; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recebimentos_qr (
    pedido_id integer NOT NULL,
    codigo character varying(43) NOT NULL,
    versao integer NOT NULL,
    url_base character varying(300) NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    recebedor_nome character varying(120),
    registro_profissional character varying(50),
    confirmado_em timestamp without time zone,
    ip_origem character varying(45)
);


--
-- Name: retiradas_pedidos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.retiradas_pedidos (
    pedido_id integer NOT NULL,
    versao integer NOT NULL,
    copeira_id integer NOT NULL,
    copeira_nome character varying(100) NOT NULL,
    registrado_por_usuario_id integer NOT NULL,
    retirada_em timestamp without time zone DEFAULT now() NOT NULL,
    ip_origem character varying(45)
);


--
-- Name: servidores_unidades; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.servidores_unidades (
    id character varying(36) NOT NULL,
    filial_id integer NOT NULL,
    url_local character varying(300) NOT NULL,
    token_hash character varying(64) NOT NULL,
    credencial_ativa boolean NOT NULL,
    operacao_ativada boolean NOT NULL,
    instalacao_uuid character varying(36),
    geracao integer NOT NULL,
    intervalo_segundos integer NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    ultimo_contato timestamp without time zone,
    ultima_publicacao timestamp without time zone,
    versao_aplicacao character varying(30),
    pedidos_pendentes integer NOT NULL,
    conflitos integer NOT NULL,
    espaco_livre_bytes bigint,
    espaco_total_bytes bigint,
    ultimo_erro character varying(300),
    cadastros jsonb,
    cadastros_sha256 character varying(64),
    cadastros_em timestamp without time zone
);


--
-- Name: sessoes_copeiras; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sessoes_copeiras (
    id character varying(36) NOT NULL,
    usuario_id integer NOT NULL,
    filial_id integer,
    presenca_ate timestamp without time zone NOT NULL,
    encerrada_em timestamp without time zone
);


--
-- Name: sessoes_usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sessoes_usuarios (
    id character varying(36) NOT NULL,
    usuario_id integer NOT NULL,
    expira_em timestamp without time zone NOT NULL,
    encerrada_em timestamp without time zone
);


--
-- Name: tentativas_publicacoes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tentativas_publicacoes (
    id integer NOT NULL,
    pedido_uuid character varying(36) NOT NULL,
    revisao bigint NOT NULL,
    sha256 character varying(64) NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: tentativas_publicacoes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tentativas_publicacoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tentativas_publicacoes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tentativas_publicacoes_id_seq OWNED BY public.tentativas_publicacoes.id;


--
-- Name: trabalhos_impressao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.trabalhos_impressao (
    id integer NOT NULL,
    pedido_id integer NOT NULL,
    tipo_documento character varying(20) DEFAULT 'FILIPETA'::character varying NOT NULL,
    configuracao jsonb,
    estado character varying(20) NOT NULL,
    tentativas integer NOT NULL,
    erro character varying(250),
    dados bytea,
    criado_em timestamp without time zone DEFAULT now() NOT NULL,
    proxima_tentativa_em timestamp without time zone NOT NULL,
    iniciado_em timestamp without time zone,
    enviado_em timestamp without time zone,
    reserva character varying(36),
    solicitado_por_usuario_id integer
);


--
-- Name: trabalhos_impressao_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.trabalhos_impressao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: trabalhos_impressao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.trabalhos_impressao_id_seq OWNED BY public.trabalhos_impressao.id;


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios (
    id integer NOT NULL,
    nome character varying(100) NOT NULL,
    nome_usuario character varying(50) NOT NULL,
    email character varying(120),
    senha_hash character varying(255) NOT NULL,
    origem_autenticacao character varying(8) DEFAULT 'LOCAL'::character varying NOT NULL,
    usuario_ad character varying(254),
    ad_object_guid character varying(36),
    perfil_id integer NOT NULL,
    ativo boolean NOT NULL,
    troca_senha_obrigatoria boolean DEFAULT false NOT NULL,
    criado_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: usuarios_filiais; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuarios_filiais (
    usuario_id integer NOT NULL,
    filial_id integer NOT NULL
);


--
-- Name: usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.usuarios_id_seq OWNED BY public.usuarios.id;


--
-- Name: versoes_consolidadas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.versoes_consolidadas (
    servidor_id character varying(36) NOT NULL,
    pedido_uuid character varying(36) NOT NULL,
    revisao bigint NOT NULL,
    sha256 character varying(64) NOT NULL,
    anterior_sha256 character varying(64),
    conteudo jsonb NOT NULL,
    recebido_em timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: auditoria_administrativa id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_administrativa ALTER COLUMN id SET DEFAULT nextval('public.auditoria_administrativa_id_seq'::regclass);


--
-- Name: avisos_email_pedidos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_email_pedidos ALTER COLUMN id SET DEFAULT nextval('public.avisos_email_pedidos_id_seq'::regclass);


--
-- Name: dietas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dietas ALTER COLUMN id SET DEFAULT nextval('public.dietas_id_seq'::regclass);


--
-- Name: estado_unidade_local id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estado_unidade_local ALTER COLUMN id SET DEFAULT nextval('public.estado_unidade_local_id_seq'::regclass);


--
-- Name: eventos_assistenciais id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_assistenciais ALTER COLUMN id SET DEFAULT nextval('public.eventos_assistenciais_id_seq'::regclass);


--
-- Name: filiais id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.filiais ALTER COLUMN id SET DEFAULT nextval('public.filiais_id_seq'::regclass);


--
-- Name: formularios_config id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.formularios_config ALTER COLUMN id SET DEFAULT nextval('public.formularios_config_id_seq'::regclass);


--
-- Name: historico_pedidos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historico_pedidos ALTER COLUMN id SET DEFAULT nextval('public.historico_pedidos_id_seq'::regclass);


--
-- Name: pedidos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos ALTER COLUMN id SET DEFAULT nextval('public.pedidos_id_seq'::regclass);


--
-- Name: perfis id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfis ALTER COLUMN id SET DEFAULT nextval('public.perfis_id_seq'::regclass);


--
-- Name: publicacoes_pedidos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.publicacoes_pedidos ALTER COLUMN id SET DEFAULT nextval('public.publicacoes_pedidos_id_seq'::regclass);


--
-- Name: tentativas_publicacoes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tentativas_publicacoes ALTER COLUMN id SET DEFAULT nextval('public.tentativas_publicacoes_id_seq'::regclass);


--
-- Name: trabalhos_impressao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trabalhos_impressao ALTER COLUMN id SET DEFAULT nextval('public.trabalhos_impressao_id_seq'::regclass);


--
-- Name: usuarios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);


--
-- Name: alteracoes_cadastros_remotas alteracoes_cadastros_remotas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alteracoes_cadastros_remotas
    ADD CONSTRAINT alteracoes_cadastros_remotas_pkey PRIMARY KEY (id);


--
-- Name: aplicacoes_cadastros_locais aplicacoes_cadastros_locais_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.aplicacoes_cadastros_locais
    ADD CONSTRAINT aplicacoes_cadastros_locais_pkey PRIMARY KEY (id);


--
-- Name: auditoria_administrativa auditoria_administrativa_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_administrativa
    ADD CONSTRAINT auditoria_administrativa_pkey PRIMARY KEY (id);


--
-- Name: avisos_email_pedidos avisos_email_pedidos_mensagem_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_email_pedidos
    ADD CONSTRAINT avisos_email_pedidos_mensagem_id_key UNIQUE (mensagem_id);


--
-- Name: avisos_email_pedidos avisos_email_pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_email_pedidos
    ADD CONSTRAINT avisos_email_pedidos_pkey PRIMARY KEY (id);


--
-- Name: comprovantes_entrega comprovantes_entrega_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprovantes_entrega
    ADD CONSTRAINT comprovantes_entrega_pkey PRIMARY KEY (pedido_id);


--
-- Name: configuracoes_email_unidades configuracoes_email_unidades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuracoes_email_unidades
    ADD CONSTRAINT configuracoes_email_unidades_pkey PRIMARY KEY (filial_id);


--
-- Name: configuracoes_operacionais configuracoes_operacionais_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuracoes_operacionais
    ADD CONSTRAINT configuracoes_operacionais_pkey PRIMARY KEY (filial_id);


--
-- Name: contatos_email_pedidos contatos_email_pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contatos_email_pedidos
    ADD CONSTRAINT contatos_email_pedidos_pkey PRIMARY KEY (pedido_id);


--
-- Name: dietas dietas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dietas
    ADD CONSTRAINT dietas_pkey PRIMARY KEY (id);


--
-- Name: entregas_pedidos entregas_pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entregas_pedidos
    ADD CONSTRAINT entregas_pedidos_pkey PRIMARY KEY (pedido_id);


--
-- Name: estado_unidade_local estado_unidade_local_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estado_unidade_local
    ADD CONSTRAINT estado_unidade_local_pkey PRIMARY KEY (id);


--
-- Name: eventos_assistenciais eventos_assistenciais_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_assistenciais
    ADD CONSTRAINT eventos_assistenciais_pkey PRIMARY KEY (id);


--
-- Name: filiais filiais_codigo_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.filiais
    ADD CONSTRAINT filiais_codigo_slug_key UNIQUE (codigo_slug);


--
-- Name: filiais filiais_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.filiais
    ADD CONSTRAINT filiais_pkey PRIMARY KEY (id);


--
-- Name: formularios_config formularios_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.formularios_config
    ADD CONSTRAINT formularios_config_pkey PRIMARY KEY (id);


--
-- Name: fotos_consolidadas fotos_consolidadas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fotos_consolidadas
    ADD CONSTRAINT fotos_consolidadas_pkey PRIMARY KEY (servidor_id, sha256);


--
-- Name: historico_pedidos historico_pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historico_pedidos
    ADD CONSTRAINT historico_pedidos_pkey PRIMARY KEY (id);


--
-- Name: impressoras_etiquetas impressoras_etiquetas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.impressoras_etiquetas
    ADD CONSTRAINT impressoras_etiquetas_pkey PRIMARY KEY (filial_id);


--
-- Name: limites_login limites_login_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.limites_login
    ADD CONSTRAINT limites_login_pkey PRIMARY KEY (chave);


--
-- Name: pedidos_consolidados pedidos_consolidados_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos_consolidados
    ADD CONSTRAINT pedidos_consolidados_pkey PRIMARY KEY (servidor_id, pedido_uuid);


--
-- Name: pedidos pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_pkey PRIMARY KEY (id);


--
-- Name: pedidos pedidos_uuid_global_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_uuid_global_key UNIQUE (uuid_global);


--
-- Name: perfis perfis_nome_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfis
    ADD CONSTRAINT perfis_nome_key UNIQUE (nome);


--
-- Name: perfis perfis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.perfis
    ADD CONSTRAINT perfis_pkey PRIMARY KEY (id);


--
-- Name: publicacoes_pedidos publicacoes_pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.publicacoes_pedidos
    ADD CONSTRAINT publicacoes_pedidos_pkey PRIMARY KEY (id);


--
-- Name: recebimentos_entregas recebimentos_entregas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recebimentos_entregas
    ADD CONSTRAINT recebimentos_entregas_pkey PRIMARY KEY (pedido_id);


--
-- Name: recebimentos_qr recebimentos_qr_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recebimentos_qr
    ADD CONSTRAINT recebimentos_qr_codigo_key UNIQUE (codigo);


--
-- Name: recebimentos_qr recebimentos_qr_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recebimentos_qr
    ADD CONSTRAINT recebimentos_qr_pkey PRIMARY KEY (pedido_id);


--
-- Name: retiradas_pedidos retiradas_pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.retiradas_pedidos
    ADD CONSTRAINT retiradas_pedidos_pkey PRIMARY KEY (pedido_id, versao);


--
-- Name: servidores_unidades servidores_unidades_filial_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.servidores_unidades
    ADD CONSTRAINT servidores_unidades_filial_id_key UNIQUE (filial_id);


--
-- Name: servidores_unidades servidores_unidades_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.servidores_unidades
    ADD CONSTRAINT servidores_unidades_pkey PRIMARY KEY (id);


--
-- Name: sessoes_copeiras sessoes_copeiras_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessoes_copeiras
    ADD CONSTRAINT sessoes_copeiras_pkey PRIMARY KEY (id);


--
-- Name: sessoes_usuarios sessoes_usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessoes_usuarios
    ADD CONSTRAINT sessoes_usuarios_pkey PRIMARY KEY (id);


--
-- Name: tentativas_publicacoes tentativas_publicacoes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tentativas_publicacoes
    ADD CONSTRAINT tentativas_publicacoes_pkey PRIMARY KEY (id);


--
-- Name: trabalhos_impressao trabalhos_impressao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trabalhos_impressao
    ADD CONSTRAINT trabalhos_impressao_pkey PRIMARY KEY (id);


--
-- Name: formularios_config unique_filial_publico; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.formularios_config
    ADD CONSTRAINT unique_filial_publico UNIQUE (filial_id, tipo_publico);


--
-- Name: avisos_email_pedidos uq_aviso_email_pedido_versao; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_email_pedidos
    ADD CONSTRAINT uq_aviso_email_pedido_versao UNIQUE (pedido_id, versao);


--
-- Name: pedidos uq_pedido_chave_envio; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT uq_pedido_chave_envio UNIQUE (filial_id, chave_envio);


--
-- Name: tentativas_publicacoes uq_tentativa_pedido_revisao; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tentativas_publicacoes
    ADD CONSTRAINT uq_tentativa_pedido_revisao UNIQUE (pedido_uuid, revisao);


--
-- Name: usuarios usuarios_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_email_key UNIQUE (email);


--
-- Name: usuarios_filiais usuarios_filiais_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_filiais
    ADD CONSTRAINT usuarios_filiais_pkey PRIMARY KEY (usuario_id, filial_id);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: versoes_consolidadas versoes_consolidadas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.versoes_consolidadas
    ADD CONSTRAINT versoes_consolidadas_pkey PRIMARY KEY (servidor_id, pedido_uuid, revisao);


--
-- Name: ix_alteracoes_cadastros_remotas_servidor_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_alteracoes_cadastros_remotas_servidor_id ON public.alteracoes_cadastros_remotas USING btree (servidor_id);


--
-- Name: ix_auditoria_filial_data; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auditoria_filial_data ON public.auditoria_administrativa USING btree (filial_id, criado_em);


--
-- Name: ix_aviso_email_fila; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aviso_email_fila ON public.avisos_email_pedidos USING btree (estado, proxima_tentativa_em);


--
-- Name: ix_consolidado_filial_data; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_consolidado_filial_data ON public.pedidos_consolidados USING btree (filial_id, criado_em);


--
-- Name: ix_evento_pedido_data; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evento_pedido_data ON public.eventos_assistenciais USING btree (pedido_id, id);


--
-- Name: ix_publicacao_pendente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_publicacao_pendente ON public.publicacoes_pedidos USING btree (tentar_apos, pedido_id);


--
-- Name: ix_publicacoes_pedidos_pedido_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_publicacoes_pedidos_pedido_uuid ON public.publicacoes_pedidos USING btree (pedido_uuid);


--
-- Name: ix_sessoes_copeiras_filial_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sessoes_copeiras_filial_id ON public.sessoes_copeiras USING btree (filial_id);


--
-- Name: ix_sessoes_copeiras_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sessoes_copeiras_usuario_id ON public.sessoes_copeiras USING btree (usuario_id);


--
-- Name: ix_sessoes_usuarios_usuario_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sessoes_usuarios_usuario_id ON public.sessoes_usuarios USING btree (usuario_id);


--
-- Name: ix_tentativas_publicacoes_pedido_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tentativas_publicacoes_pedido_uuid ON public.tentativas_publicacoes USING btree (pedido_uuid);


--
-- Name: ix_trabalhos_impressao_estado; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trabalhos_impressao_estado ON public.trabalhos_impressao USING btree (estado);


--
-- Name: ix_trabalhos_impressao_pedido_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_trabalhos_impressao_pedido_id ON public.trabalhos_impressao USING btree (pedido_id);


--
-- Name: uq_impressao_ativa_tipo; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_impressao_ativa_tipo ON public.trabalhos_impressao USING btree (pedido_id, tipo_documento) WHERE ((estado)::text = ANY ((ARRAY['PENDENTE'::character varying, 'PROCESSANDO'::character varying])::text[]));


--
-- Name: uq_usuarios_ad; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_usuarios_ad ON public.usuarios USING btree (lower((usuario_ad)::text));


--
-- Name: uq_usuarios_ad_guid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_usuarios_ad_guid ON public.usuarios USING btree (ad_object_guid);


--
-- Name: uq_usuarios_nome_usuario; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_usuarios_nome_usuario ON public.usuarios USING btree (lower((nome_usuario)::text));


--
-- Name: configuracoes_operacionais demeter_cadastro_configuracoes_operacionais; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_cadastro_configuracoes_operacionais BEFORE INSERT OR DELETE OR UPDATE ON public.configuracoes_operacionais FOR EACH ROW EXECUTE FUNCTION public.demeter_cadastro_da_unidade();


--
-- Name: dietas demeter_cadastro_dietas; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_cadastro_dietas BEFORE INSERT OR DELETE OR UPDATE ON public.dietas FOR EACH ROW EXECUTE FUNCTION public.demeter_cadastro_da_unidade();


--
-- Name: formularios_config demeter_cadastro_formularios_config; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_cadastro_formularios_config BEFORE INSERT OR DELETE OR UPDATE ON public.formularios_config FOR EACH ROW EXECUTE FUNCTION public.demeter_cadastro_da_unidade();


--
-- Name: impressoras_etiquetas demeter_cadastro_impressoras_etiquetas; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_cadastro_impressoras_etiquetas BEFORE INSERT OR DELETE OR UPDATE ON public.impressoras_etiquetas FOR EACH ROW EXECUTE FUNCTION public.demeter_cadastro_da_unidade();


--
-- Name: comprovantes_entrega demeter_capturar_comprovantes_entrega; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_capturar_comprovantes_entrega AFTER INSERT OR DELETE OR UPDATE ON public.comprovantes_entrega FOR EACH ROW EXECUTE FUNCTION public.demeter_capturar_pedido();


--
-- Name: dietas demeter_capturar_dieta; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_capturar_dieta AFTER UPDATE OF nome ON public.dietas FOR EACH ROW EXECUTE FUNCTION public.demeter_dieta_alterada();


--
-- Name: entregas_pedidos demeter_capturar_entregas_pedidos; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_capturar_entregas_pedidos AFTER INSERT OR DELETE OR UPDATE ON public.entregas_pedidos FOR EACH ROW EXECUTE FUNCTION public.demeter_capturar_pedido();


--
-- Name: eventos_assistenciais demeter_capturar_eventos_assistenciais; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_capturar_eventos_assistenciais AFTER INSERT OR DELETE OR UPDATE ON public.eventos_assistenciais FOR EACH ROW EXECUTE FUNCTION public.demeter_capturar_pedido();


--
-- Name: historico_pedidos demeter_capturar_historico_pedidos; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_capturar_historico_pedidos AFTER INSERT OR DELETE OR UPDATE ON public.historico_pedidos FOR EACH ROW EXECUTE FUNCTION public.demeter_capturar_pedido();


--
-- Name: pedidos demeter_capturar_pedidos; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_capturar_pedidos AFTER INSERT OR DELETE OR UPDATE ON public.pedidos FOR EACH ROW EXECUTE FUNCTION public.demeter_capturar_pedido();


--
-- Name: recebimentos_entregas demeter_capturar_recebimentos_entregas; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_capturar_recebimentos_entregas AFTER INSERT OR DELETE OR UPDATE ON public.recebimentos_entregas FOR EACH ROW EXECUTE FUNCTION public.demeter_capturar_pedido();


--
-- Name: recebimentos_qr demeter_capturar_recebimentos_qr; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_capturar_recebimentos_qr AFTER INSERT OR DELETE OR UPDATE ON public.recebimentos_qr FOR EACH ROW EXECUTE FUNCTION public.demeter_capturar_pedido();


--
-- Name: retiradas_pedidos demeter_capturar_retiradas_pedidos; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_capturar_retiradas_pedidos AFTER INSERT OR DELETE OR UPDATE ON public.retiradas_pedidos FOR EACH ROW EXECUTE FUNCTION public.demeter_capturar_pedido();


--
-- Name: trabalhos_impressao demeter_capturar_trabalhos_impressao; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_capturar_trabalhos_impressao AFTER INSERT OR DELETE OR UPDATE ON public.trabalhos_impressao FOR EACH ROW EXECUTE FUNCTION public.demeter_capturar_pedido();


--
-- Name: filiais demeter_filial_local; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_filial_local AFTER INSERT ON public.filiais FOR EACH ROW EXECUTE FUNCTION public.demeter_unica_filial_local();


--
-- Name: comprovantes_entrega demeter_validar_comprovantes_entrega; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_validar_comprovantes_entrega BEFORE INSERT OR DELETE OR UPDATE ON public.comprovantes_entrega FOR EACH ROW EXECUTE FUNCTION public.demeter_validar_pedido_operacao();


--
-- Name: entregas_pedidos demeter_validar_entregas_pedidos; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_validar_entregas_pedidos BEFORE INSERT OR DELETE OR UPDATE ON public.entregas_pedidos FOR EACH ROW EXECUTE FUNCTION public.demeter_validar_pedido_operacao();


--
-- Name: eventos_assistenciais demeter_validar_eventos_assistenciais; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_validar_eventos_assistenciais BEFORE INSERT OR DELETE OR UPDATE ON public.eventos_assistenciais FOR EACH ROW EXECUTE FUNCTION public.demeter_validar_pedido_operacao();


--
-- Name: historico_pedidos demeter_validar_historico_pedidos; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_validar_historico_pedidos BEFORE INSERT OR DELETE OR UPDATE ON public.historico_pedidos FOR EACH ROW EXECUTE FUNCTION public.demeter_validar_pedido_operacao();


--
-- Name: pedidos demeter_validar_pedidos; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_validar_pedidos BEFORE INSERT OR DELETE OR UPDATE ON public.pedidos FOR EACH ROW EXECUTE FUNCTION public.demeter_validar_pedido_operacao();


--
-- Name: recebimentos_entregas demeter_validar_recebimentos_entregas; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_validar_recebimentos_entregas BEFORE INSERT OR DELETE OR UPDATE ON public.recebimentos_entregas FOR EACH ROW EXECUTE FUNCTION public.demeter_validar_pedido_operacao();


--
-- Name: recebimentos_qr demeter_validar_recebimentos_qr; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_validar_recebimentos_qr BEFORE INSERT OR DELETE OR UPDATE ON public.recebimentos_qr FOR EACH ROW EXECUTE FUNCTION public.demeter_validar_pedido_operacao();


--
-- Name: retiradas_pedidos demeter_validar_retiradas_pedidos; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_validar_retiradas_pedidos BEFORE INSERT OR DELETE OR UPDATE ON public.retiradas_pedidos FOR EACH ROW EXECUTE FUNCTION public.demeter_validar_pedido_operacao();


--
-- Name: trabalhos_impressao demeter_validar_trabalhos_impressao; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER demeter_validar_trabalhos_impressao BEFORE INSERT OR DELETE OR UPDATE ON public.trabalhos_impressao FOR EACH ROW EXECUTE FUNCTION public.demeter_validar_pedido_operacao();


--
-- Name: alteracoes_cadastros_remotas alteracoes_cadastros_remotas_servidor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alteracoes_cadastros_remotas
    ADD CONSTRAINT alteracoes_cadastros_remotas_servidor_id_fkey FOREIGN KEY (servidor_id) REFERENCES public.servidores_unidades(id) ON DELETE RESTRICT;


--
-- Name: auditoria_administrativa auditoria_administrativa_autor_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_administrativa
    ADD CONSTRAINT auditoria_administrativa_autor_usuario_id_fkey FOREIGN KEY (autor_usuario_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: auditoria_administrativa auditoria_administrativa_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_administrativa
    ADD CONSTRAINT auditoria_administrativa_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE RESTRICT;


--
-- Name: avisos_email_pedidos avisos_email_pedidos_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_email_pedidos
    ADD CONSTRAINT avisos_email_pedidos_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE RESTRICT;


--
-- Name: avisos_email_pedidos avisos_email_pedidos_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.avisos_email_pedidos
    ADD CONSTRAINT avisos_email_pedidos_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id) ON DELETE RESTRICT;


--
-- Name: comprovantes_entrega comprovantes_entrega_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprovantes_entrega
    ADD CONSTRAINT comprovantes_entrega_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.recebimentos_qr(pedido_id) ON DELETE RESTRICT;


--
-- Name: comprovantes_entrega comprovantes_entrega_registrado_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comprovantes_entrega
    ADD CONSTRAINT comprovantes_entrega_registrado_por_usuario_id_fkey FOREIGN KEY (registrado_por_usuario_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: configuracoes_email_unidades configuracoes_email_unidades_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuracoes_email_unidades
    ADD CONSTRAINT configuracoes_email_unidades_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE RESTRICT;


--
-- Name: configuracoes_operacionais configuracoes_operacionais_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuracoes_operacionais
    ADD CONSTRAINT configuracoes_operacionais_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE CASCADE;


--
-- Name: contatos_email_pedidos contatos_email_pedidos_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contatos_email_pedidos
    ADD CONSTRAINT contatos_email_pedidos_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id) ON DELETE RESTRICT;


--
-- Name: dietas dietas_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dietas
    ADD CONSTRAINT dietas_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE CASCADE;


--
-- Name: entregas_pedidos entregas_pedidos_copeira_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entregas_pedidos
    ADD CONSTRAINT entregas_pedidos_copeira_id_fkey FOREIGN KEY (copeira_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: entregas_pedidos entregas_pedidos_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entregas_pedidos
    ADD CONSTRAINT entregas_pedidos_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id) ON DELETE RESTRICT;


--
-- Name: entregas_pedidos entregas_pedidos_registrado_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entregas_pedidos
    ADD CONSTRAINT entregas_pedidos_registrado_por_usuario_id_fkey FOREIGN KEY (registrado_por_usuario_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: estado_unidade_local estado_unidade_local_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.estado_unidade_local
    ADD CONSTRAINT estado_unidade_local_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE RESTRICT;


--
-- Name: eventos_assistenciais eventos_assistenciais_autor_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_assistenciais
    ADD CONSTRAINT eventos_assistenciais_autor_usuario_id_fkey FOREIGN KEY (autor_usuario_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: eventos_assistenciais eventos_assistenciais_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_assistenciais
    ADD CONSTRAINT eventos_assistenciais_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id) ON DELETE RESTRICT;


--
-- Name: formularios_config formularios_config_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.formularios_config
    ADD CONSTRAINT formularios_config_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE CASCADE;


--
-- Name: fotos_consolidadas fotos_consolidadas_servidor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fotos_consolidadas
    ADD CONSTRAINT fotos_consolidadas_servidor_id_fkey FOREIGN KEY (servidor_id) REFERENCES public.servidores_unidades(id) ON DELETE RESTRICT;


--
-- Name: historico_pedidos historico_pedidos_alterado_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historico_pedidos
    ADD CONSTRAINT historico_pedidos_alterado_por_usuario_id_fkey FOREIGN KEY (alterado_por_usuario_id) REFERENCES public.usuarios(id) ON DELETE SET NULL;


--
-- Name: historico_pedidos historico_pedidos_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historico_pedidos
    ADD CONSTRAINT historico_pedidos_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id) ON DELETE CASCADE;


--
-- Name: impressoras_etiquetas impressoras_etiquetas_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.impressoras_etiquetas
    ADD CONSTRAINT impressoras_etiquetas_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE CASCADE;


--
-- Name: pedidos_consolidados pedidos_consolidados_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos_consolidados
    ADD CONSTRAINT pedidos_consolidados_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE RESTRICT;


--
-- Name: pedidos_consolidados pedidos_consolidados_servidor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos_consolidados
    ADD CONSTRAINT pedidos_consolidados_servidor_id_fkey FOREIGN KEY (servidor_id) REFERENCES public.servidores_unidades(id) ON DELETE RESTRICT;


--
-- Name: pedidos pedidos_dieta_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_dieta_id_fkey FOREIGN KEY (dieta_id) REFERENCES public.dietas(id) ON DELETE SET NULL;


--
-- Name: pedidos pedidos_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE RESTRICT;


--
-- Name: recebimentos_entregas recebimentos_entregas_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recebimentos_entregas
    ADD CONSTRAINT recebimentos_entregas_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.entregas_pedidos(pedido_id) ON DELETE RESTRICT;


--
-- Name: recebimentos_qr recebimentos_qr_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recebimentos_qr
    ADD CONSTRAINT recebimentos_qr_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id) ON DELETE RESTRICT;


--
-- Name: retiradas_pedidos retiradas_pedidos_copeira_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.retiradas_pedidos
    ADD CONSTRAINT retiradas_pedidos_copeira_id_fkey FOREIGN KEY (copeira_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: retiradas_pedidos retiradas_pedidos_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.retiradas_pedidos
    ADD CONSTRAINT retiradas_pedidos_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id) ON DELETE RESTRICT;


--
-- Name: retiradas_pedidos retiradas_pedidos_registrado_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.retiradas_pedidos
    ADD CONSTRAINT retiradas_pedidos_registrado_por_usuario_id_fkey FOREIGN KEY (registrado_por_usuario_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: servidores_unidades servidores_unidades_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.servidores_unidades
    ADD CONSTRAINT servidores_unidades_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE RESTRICT;


--
-- Name: sessoes_copeiras sessoes_copeiras_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessoes_copeiras
    ADD CONSTRAINT sessoes_copeiras_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE CASCADE;


--
-- Name: sessoes_copeiras sessoes_copeiras_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessoes_copeiras
    ADD CONSTRAINT sessoes_copeiras_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: sessoes_usuarios sessoes_usuarios_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sessoes_usuarios
    ADD CONSTRAINT sessoes_usuarios_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: trabalhos_impressao trabalhos_impressao_pedido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trabalhos_impressao
    ADD CONSTRAINT trabalhos_impressao_pedido_id_fkey FOREIGN KEY (pedido_id) REFERENCES public.pedidos(id) ON DELETE RESTRICT;


--
-- Name: trabalhos_impressao trabalhos_impressao_solicitado_por_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trabalhos_impressao
    ADD CONSTRAINT trabalhos_impressao_solicitado_por_usuario_id_fkey FOREIGN KEY (solicitado_por_usuario_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: usuarios_filiais usuarios_filiais_filial_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_filiais
    ADD CONSTRAINT usuarios_filiais_filial_id_fkey FOREIGN KEY (filial_id) REFERENCES public.filiais(id) ON DELETE CASCADE;


--
-- Name: usuarios_filiais usuarios_filiais_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios_filiais
    ADD CONSTRAINT usuarios_filiais_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: usuarios usuarios_perfil_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_perfil_id_fkey FOREIGN KEY (perfil_id) REFERENCES public.perfis(id) ON DELETE RESTRICT;


--
-- Name: versoes_consolidadas versoes_consolidadas_servidor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.versoes_consolidadas
    ADD CONSTRAINT versoes_consolidadas_servidor_id_fkey FOREIGN KEY (servidor_id) REFERENCES public.servidores_unidades(id) ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

\unrestrict WN2HGhjMbhNYw0bCT8e2apAUKSD7YugTrJa8TGhtWlvANgfCBdRecGvUGKaKjQj
