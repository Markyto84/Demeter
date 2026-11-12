# Deméter — Gestão de Nutrição

**Nutrição e cuidado em cada etapa.**

O Deméter reúne a solicitação de refeições, o preparo na cozinha, a impressão e a
comprovação de entrega das unidades hospitalares. A versão **0.1.1** está preparada
para uma instalação nova com banco limpo, sem transportar os dados da estação de desenvolvimento.

## Funcionalidades disponíveis

| Área | O que permite fazer |
| --- | --- |
| Formulário por unidade | Solicitações de Médico/Administração e Enfermagem/Paciente; dietas, acompanhante, cardápios e campos configuráveis. |
| Cozinha | Kanban sem login na intranet; iniciar preparo, marcar pronto, cancelar com motivo, pesquisar, filtrar e acompanhar alertas de prazo. |
| Impressão | Filipetas com os dados do formulário, acentos e identificação do solicitante; etiquetas de 89 × 36 mm somente quando a refeição está pronta. |
| Comprovação de entrega | Filipeta com nome do recebedor, assinatura e data/hora no papel. A Nutrição acessa o QR Code, autentica, lança os dados e anexa a foto. |
| Gestão de Nutrição | Dietas, cardápios, formulários e prazos por unidade; consulta e relatórios por período. |
| Administração de TI | Unidades, atalhos, usuários, perfis e vínculos; impressoras, SMTP por unidade, monitoramento e auditoria. |
| Relatórios | Filtros por unidade e período, rastreabilidade e comprovantes; exportação XLSX, ODS e CSV para importação no Google Sheets. |
| Avisos médicos | E-mail ao marcar a refeição como pronta, com resumo da solicitação. Transporte SMTP configurável por unidade, fila e tratamento de falhas. |

Os painéis recebem atualizações WebSocket, com reconciliação periódica e recuperação
de falhas. Solicitações e tarefas de impressão são persistidas juntas; o envio pela
rede ocorre em segundo plano. Um envio incerto exige conferência antes de repetir.

O painel de entregas das copeiras está **desativado no fluxo atual**. O perfil
Copeira e registros anteriores permanecem preservados. A finalização de entrega é
feita pela Nutrição ou pelo Administrador de TI, com acesso à unidade. Veja
[comprovação de entrega](RECEBIMENTO-POR-QR.md).

## Instalação nova com banco limpo

A primeira inicialização cria somente:

- Quatro perfis: `ADMIN_TI`, `NUTRICIONISTA`, `COZINHA` e `COPEIRA`.
- Uma conta `admin`, com senha temporária exclusiva e troca obrigatória no primeiro acesso.
- A estrutura das tabelas e seus índices.

Não cria unidades, dietas, formulários de unidade, pacientes, pedidos, fotos,
entregas, impressoras ou contas SMTP de demonstração. Reiniciar antes do cadastro
da primeira unidade preserva o administrador e sua senha.

O caminho recomendado é o [instalador Linux](DISTRIBUICAO-LINUX.md). Os arquivos da
versão ficam nas [releases do GitHub](https://github.com/Markyto84/Demeter/releases).
O instalador prepara um volume PostgreSQL novo e recusa substituir uma instalação
existente. Não copia, apaga nem redefine o banco desta estação.

A TI também dispõe do [esquema SQL sem registros](infra/banco/README.md), como
alternativa para um PostgreSQL 16 novo e vazio. O instalador não exige importar esse
SQL manualmente. Consulte o [roteiro de produção limpa](PRODUCAO-LIMPA.md).

### Primeiro acesso

1. Instale o pacote em um servidor Linux Intel/AMD 64 bits com Docker Engine e o plugin Compose.
2. Informe o endereço pelo qual os dispositivos acessarão o servidor.
3. Consulte `work/credencial-inicial.txt` **no servidor instalado** e entre em `/login`.
4. Troque a senha temporária. Em Administração → Unidades, cadastre a primeira unidade.
5. Revise os modelos dos dois formulários criados para a unidade; configure dietas, cardápios, prazos, impressoras, SMTP e os acessos da equipe.
6. Baixe os atalhos por unidade e conclua a [homologação](HOMOLOGACAO-LINUX.md).

Cada instalação recebe seus próprios segredos e credenciais. Arquivos `.env`,
senhas, certificados, fotos, dumps, backups e logs locais ficam fora do Git e do
instalador. O repositório público contém o código e os modelos da aplicação.

## Endereços

Os links usam o IP ou DNS configurado na instalação:

| Acesso | Caminho |
| --- | --- |
| Login | `/login` |
| Administração | `/admin` |
| Gestão de Nutrição | `/gestao` |
| Formulário da unidade | `/{codigo-da-unidade}` |
| Cozinha da unidade | `/cozinha/{codigo-da-unidade}` |
| Recebimento pela Nutrição | `/receber`, aberto pelo QR Code da filipeta |

Exemplo de código de unidade: `unidade-havai`. Em uma instalação limpa, esses links
só ficam disponíveis depois que a unidade é cadastrada. O endereço `/entregas/{id}`
apresenta a orientação sobre o fluxo de entrega atual.

## Executar a partir do código

**Stack:** FastAPI e Python 3.12; React, Vite e Tailwind CSS; PostgreSQL 16;
WebSockets; impressão TCP e Docker.

Em Linux, o assistente prepara o endereço e as configurações privadas:

```sh
sh ./servidor.sh configurar
sh ./servidor.sh validar
sh ./servidor.sh iniciar
```

Em Windows, com Docker Desktop, Python e Node.js disponíveis:

```powershell
.\start.ps1
# Acesso inicial: http://localhost:5173/login
.\stop.ps1
```

O ambiente Windows usa PostgreSQL na porta 5433, API na 8000 e interface na 5173.
O Compose de desenvolvimento mantém sua identidade de volume para preservar a base
existente. A opção de demonstração é desativada por padrão; só pode ser habilitada
explicitamente no desenvolvimento com `INICIALIZAR_DEMONSTRACAO=true`. Produção rejeita essa opção.

A instalação de trabalho nesta estação fica em
`C:\Users\Suporte\Documents\Projeto Demeter`. Alterações em andamento usam worktrees
separados, sem executar uma segunda instalação contra o mesmo banco.

## Limites e preparação para produção

- A API opera com **um worker**, pois os eventos WebSocket estão em memória.
- A arquitetura atual usa servidor central. Servidores locais por unidade com sincronização e operação independente ainda fazem parte do planejamento.
- O HTTPS está preparado e será ativado pela TI no servidor definitivo. A integração com AD local permanece desativada até a configuração de LDAPS e dos certificados.
- Impressoras por IP, entrega real do e-mail, acesso dos celulares ao QR Code e recuperação de backup precisam ser homologados no ambiente de destino.
- Backups devem ter retenção e cópia externa. A rotina de validação testa a restauração em banco temporário, sem substituir a base de origem.

## Documentação e validação

- [Revisão de 12/11/2026](REVISAO-APLICACAO-2026-11-12.md).
- [Instalação e endereço do servidor](INSTALACAO-SERVIDOR.md).
- [Distribuição executável Linux](DISTRIBUICAO-LINUX.md) e [banco limpo](PRODUCAO-LIMPA.md).
- [Homologação no Linux](HOMOLOGACAO-LINUX.md), [HTTPS](HTTPS.md) e [Active Directory](ACTIVE-DIRECTORY.md).
- [Monitoramento e recuperação](MONITORAMENTO-E-RECUPERACAO.md).
- [Avisos por e-mail](AVISOS-EMAIL-MEDICO.md), [cozinha sem login](COZINHA-SEM-LOGIN.md) e [atalhos por unidade](ATALHOS-UNIDADES.md).
- [Sincronização dos painéis](SINCRONIZACAO-OPERACIONAL.md), [rastreabilidade](PRESCRICOES-E-RASTREABILIDADE.md) e [linguagem visual](UI-ACOLHIMENTO.md).

No frontend, execute `npm ci`, `npm test`, `npm run lint` e `npm run build`.
No backend, instale `requirements-dev.txt` em um ambiente de teste e execute
`python -m unittest discover -s tests -v`. Para testes PostgreSQL, use somente uma
base descartável em `DEMETER_TEST_POSTGRES_URL`. Os testes externos informam suas
variáveis de habilitação nos próprios módulos.
