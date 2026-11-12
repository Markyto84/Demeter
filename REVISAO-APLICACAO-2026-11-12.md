# Deméter — revisão de 12/11/2026

A aplicação foi revisada para consolidar a versão 0.1.1 e preparar uma nova instalação
sem dados anteriores. O banco usado nesta estação foi preservado. A revisão abrangeu
código, inicialização, fluxos, testes automatizados, exportação da estrutura do banco,
distribuição e documentação. Não foi realizado novo teste de carga nesta revisão.

## Correções incorporadas

| Item identificado | Resultado |
| --- | --- |
| Uma base vazia criava unidade e dietas de demonstração. | Novas bases recebem somente quatro perfis e um administrador de TI com troca obrigatória da senha temporária. |
| A inicialização usava a existência de unidades para decidir se já havia sido executada. | Agora também verifica os usuários; reiniciar antes do cadastro da primeira unidade preserva a conta, sua senha e ativação. |
| A preparação de produção limpa estava em um worktree anterior, fora da versão publicada. | Alterações integradas ao código atual, preservando a marca Deméter, SMTP por unidade e o fluxo manual de comprovação. |
| Documentos descreviam a entrega antiga das copeiras como fluxo vigente. | README, recebimento e documento de continuidade atualizados para filipeta assinada e foto registrada pela Nutrição. |
| O instalador podia informar uma revisão Git sem exigir que as alterações estivessem registradas. | A geração agora recusa fontes com alterações pendentes antes de compilar. |
| A auditoria npm apontou `follow-redirects` 1.16.1, uma dependência indireta. | Arquivo de dependências atualizado para 1.16.3; nova instalação, testes e auditoria repetidos, sem alertas npm. |
| A auditoria Python apontou avisos nas dependências de autenticação e suporte. | Autenticação migrada para PyJWT, preservando tokens HS256 anteriores; pyasn1 atualizado e pip atualizado na imagem. Ambiente novo auditado sem avisos. |

O [aviso do mantenedor de follow-redirects](https://github.com/follow-redirects/follow-redirects/security/advisories/GHSA-mrwp-f3q8-3g9p)
identifica a correção a partir de 1.16.2. O alerta no pacote indireto não demonstra
exploração no Deméter; a atualização remove a versão afetada do conjunto de dependências.

A validação JWT mantém o algoritmo permitido na configuração e exige expiração,
identificação do usuário e da sessão. Um teste utiliza token fictício emitido pela
biblioteca anterior para conferir a compatibilidade. A nova biblioteca segue a
[API documentada do PyJWT](https://pyjwt.readthedocs.io/en/stable/api.html).

## Estado funcional

- **Solicitação:** formulários por unidade, identificação do solicitante, regras de paciente/acompanhante, dieta geral do acompanhante, cardápios e escolhas médicas configuráveis.
- **Cozinha:** operação sem login na intranet, etapas do preparo, cancelamento com motivo, busca, filtros, alertas e sincronização WebSocket com reconciliação.
- **Filipetas e etiquetas:** fila persistente, tratamento de envio incerto, renderização dos acentos e etiquetas somente no status Pronto; identidade Deméter.
- **Entrega:** nome, assinatura, data e hora no papel; Nutrição/TI autentica pelo QR Code, informa os dados e anexa a foto. O painel de copeiras está desativado.
- **Fotos:** JPEG normalizado de até 300 KiB, sem guardar o original, com orientação corrigida, integridade e dimensões registradas.
- **E-mail médico:** campo do solicitante, aviso de refeição pronta e resumo; SMTP por unidade, credencial cifrada, configuração de segurança e tratamento de falhas.
- **Gestão e TI:** unidades, atalhos, catálogos, formulários, prazos, credenciais, perfis, impressoras, monitoramento e auditoria; histórico administrativo restrito à TI.
- **Relatórios:** filtros por período e unidade, responsáveis e horários; XLSX, ODS e CSV. Google Sheets usa importação do CSV, sem publicação automática dos dados.

## Validações desta revisão

- Backend: **375 testes**, sendo **374 aprovados** e um teste externo de Caddy omitido por não haver executável indicado. Os casos PostgreSQL e Docker foram habilitados em contêiner de teste exclusivo.
- Interface: **87 testes aprovados**, compilação concluída e lint sem erros. Permanecem dois avisos anteriores de dependências de efeitos em `Gestao.jsx`.
- Banco novo: inicialização completa em PostgreSQL 16.15, duas partidas consecutivas, quatro perfis, um administrador e nenhuma unidade ou registro operacional.
- SQL separado: exportação somente da estrutura, restaurada em outro banco vazio; **24 tabelas e zero registros**. Sem contas, senhas, pacientes, fotos ou configuração SMTP.
- Banco atual: backup testado por restauração, com **24 tabelas, 494 registros, cinco assinaturas, seis formulários e onze sequências conferidos**. A base de origem foi preservada.
- Auditoria npm após atualização: nenhum alerta reportado. Esse resultado é uma consulta às bases de avisos, não uma certificação de segurança.
- Auditoria Python no ambiente novo de validação: nenhum aviso conhecido reportado; consistência das dependências conferida com `pip check`.
- O resultado da prova do instalador Linux e os hashes dos arquivos distribuídos acompanham a release.

Testes automatizados de impressão e SMTP usam dados fictícios e transporte simulado.
Não foram enviados pedidos, e-mails ou impressões reais para validar esta versão.

## Preparação da instalação

O instalador não exporta volumes nem dados da instalação atual. Gera segredos exclusivos
no destino e mantém a senha temporária somente em arquivo privado no servidor. A TI
cadastra a primeira unidade e revisa dietas, formulários, impressoras, SMTP e permissões.
O [esquema SQL](infra/banco/README.md) é uma alternativa para banco novo; não deve ser
importado sobre uma instalação em uso. Veja [produção limpa](PRODUCAO-LIMPA.md).

## Próximas etapas

1. **Servidor de destino:** concluir DNS e HTTPS com a TI; habilitar AD/LDAPS somente após configurar e homologar os certificados e o acesso ao diretório.
2. **Piloto na unidade:** validar impressão física, chegada real dos e-mails, leitura de QR Code e envio da foto nos dispositivos usados pela equipe.
3. **Operação:** definir responsáveis por atualização, cópia externa de backup, retenção de fotos/dados e restauração periódica no Linux.
4. **Expansão:** repetir carga com a versão e o servidor finais, incluindo fotos, relatórios e SMTP. O [ensaio anterior](TESTE-DE-PICO-2026-10-28.md) é referência histórica, não validação desta versão.
5. **Evolução técnica:** automatizar os testes no GitHub, organizar migrações versionadas e, quando necessário, compartilhar eventos entre processos. A API atual mantém um worker.

A arquitetura com servidores locais em cada unidade e consolidação central **ainda não
está implementada**. Ela exige identidade global de registros, fila persistente de
sincronização, tratamento de conflitos, monitoramento e recuperação por unidade.
O produto atual usa um servidor central; instalar um atalho ou abrir no celular não
cria um servidor local nem permite operação independente quando a conexão é interrompida.
