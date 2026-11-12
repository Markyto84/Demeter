--
-- PostgreSQL database dump
--

\restrict 4geRk77pjFGVqqbFMq8tVyEgSQPrh6USJxbfuH3Xr2JF0xKLk2M5ajKV44LMnoX

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

SET default_tablespace = '';

SET default_table_access_method = heap;

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
-- Name: trabalhos_impressao id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.trabalhos_impressao ALTER COLUMN id SET DEFAULT nextval('public.trabalhos_impressao_id_seq'::regclass);


--
-- Name: usuarios id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);


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
-- Name: pedidos pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_pkey PRIMARY KEY (id);


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
-- Name: ix_auditoria_filial_data; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_auditoria_filial_data ON public.auditoria_administrativa USING btree (filial_id, criado_em);


--
-- Name: ix_aviso_email_fila; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_aviso_email_fila ON public.avisos_email_pedidos USING btree (estado, proxima_tentativa_em);


--
-- Name: ix_evento_pedido_data; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_evento_pedido_data ON public.eventos_assistenciais USING btree (pedido_id, id);


--
-- Name: ix_impressao_data_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_impressao_data_id ON public.trabalhos_impressao USING btree (criado_em, id);


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
-- PostgreSQL database dump complete
--

\unrestrict 4geRk77pjFGVqqbFMq8tVyEgSQPrh6USJxbfuH3Xr2JF0xKLk2M5ajKV44LMnoX

