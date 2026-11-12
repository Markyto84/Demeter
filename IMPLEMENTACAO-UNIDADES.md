# Deméter - implantação de servidores por unidade

Manual de implantação e operação - módulo de unidades, versão 0.2.0.

## 1. O que muda

Cada unidade passa a ter uma instalação completa do Deméter: aplicação, PostgreSQL,
configurações, usuários e filas de impressão. Os computadores, celulares e tablets
acessam esse servidor pela rede local. A central recebe cópias para relatórios e
acompanhamento. **A solicitação e a entrega não esperam resposta da central.**

Uma interrupção no enlace entre unidade e central mantém o atendimento local após a
ativação inicial. A fila fica no banco da unidade e é reenviada quando a conexão
voltar. Isso pressupõe que energia, servidor, rede local e equipamentos da unidade
continuem funcionando. Não há troca automática de servidor em caso de falha física.

| Papel da instalação | Responsabilidade |
| --- | --- |
| Independente | Fluxo atual, com todas as unidades na mesma instalação. É o padrão e continua disponível. |
| Central | Consolidação da rede e acompanhamento dos servidores; pode manter o atendimento de unidades ainda não transferidas. |
| Unidade | Um servidor para uma única unidade, com atendimento e cadastros locais e sincronização de saída. |

**Um único servidor é responsável pela escrita dos pedidos de cada unidade.** A
ativação bloqueia novas solicitações e alterações operacionais daquela unidade no
central. Os registros anteriores permanecem no central para consulta. Não se deve
apontar usuários ao central como contingência de uma unidade já transferida.

## 2. Cadastros administrados nas duas pontas

As equipes da unidade continuam utilizando os painéis de Gestão de Nutrição e
Administração. A central pode enviar alterações por **Servidores das unidades >
Cadastros da unidade**, ou pela Gestão de Nutrição da unidade vinculada.

| Cadastro | Unidade | Central |
| --- | --- | --- |
| Dietas, cardápios e opções dos formulários | Edição local normal | Proposta de alteração com confirmação de aplicação |
| Estrutura dos campos | Administrador de TI | Administrador de TI |
| Prazos de preparo e entrega | Gestão/TI | Gestão/TI |
| Impressoras de filipetas e etiquetas | TI | TI envia a configuração; o teste físico é feito na unidade |
| Criar usuário local com senha temporária | TI | TI envia a criação; troca obrigatória no primeiro acesso |
| Nome, perfil e situação de usuário existente | TI | TI envia a alteração |
| Redefinição de senha, renomear usuário ou mudar vínculo AD existente | TI local | Acesso direto ao painel da unidade |
| SMTP, segredos e integração AD do servidor | TI local | Acesso direto ao painel/servidor da unidade |

A central mostra a última versão recebida dos cadastros. Cada proposta guarda a
base que foi editada, autor e motivo. Se a unidade tiver modificado o mesmo cadastro
antes de recebê-la, a proposta termina em **Revisão necessária**; o sistema preserva
o cadastro local. Atualize a tela, compare com a equipe e envie outra proposta.
Não existe botão para forçar a sobrescrita de um conflito.

Uma alteração é **Aguardando unidade** até que o recibo de aplicação volte ao
central. A confirmação pode chegar no contato seguinte; não significa publicação
imediata. Não envie novamente uma criação que ainda esteja pendente.

As contas de acesso são próprias de cada instalação. Uma conta criada no central
para acessar relatórios não é automaticamente uma conta operacional da unidade.
As senhas dos usuários locais e seus hashes não são enviados na consolidação.
Somente a senha temporária de uma nova conta proposta pela TI é transportada por
HTTPS, protegida no banco central enquanto aguarda aplicação e eliminada da fila
central após a confirmação.

## 3. Preparação da infraestrutura

Antes do piloto, a TI deve definir:

1. Um servidor central e um servidor por unidade piloto, com armazenamento persistente.
2. Ubuntu Server LTS ou outra distribuição Linux compatível com Docker Engine e Compose v2.
3. DNS local acessível nos dispositivos da unidade, inclusive quando o enlace externo cair.
4. Um endereço estável por servidor. Exemplos deste manual são ilustrativos:
   `https://central.hospital.exemplo.local` e `https://havai.hospital.exemplo.local`.
5. HTTPS válido para o central. Pode usar a autoridade certificadora interna da TI,
   com a CA instalada no servidor da unidade. Para os navegadores, distribua também
   a confiança nos certificados dos endereços que eles acessam.
6. Comunicação de saída da unidade para o central, normalmente TCP 443. A central
   não precisa abrir conexão de entrada para a aplicação da unidade.
7. Rede local para impressoras IP, normalmente TCP 9100, e acesso ao SMTP configurado.
8. Relógios sincronizados por NTP e rotina de backup local com cópia fora do servidor.

Como referência inicial de homologação, use 4 vCPUs e 8 GB de RAM por instalação,
com SSD e espaço dimensionado para dados, fotos, backups e crescimento. Essa é uma
referência de teste, não um limite certificado de capacidade. Meça a carga do piloto
antes de expandir. Evite compartilhar o disco do PostgreSQL com tarefas intensas.

O banco não precisa ficar exposto na rede. Somente o proxy web publica as portas
da aplicação. Restrinja o acesso à intranet/VPN e aos equipamentos autorizados.

**Não é necessário instalar um programa em cada celular ou computador.** Eles usam
o navegador para acessar o servidor local. O serviço instalado por unidade é que
mantém aplicação, banco e sincronização funcionando.

## 4. Preparar a versão

Utilize o código ou um pacote que contenha o módulo **0.2.0**, juntamente com este
manual. O instalador anterior 0.1.1 não contém os servidores das unidades. Preserve
a versão anterior, o backup e os arquivos privados antes de atualizar uma instalação.

Para implantação pelo código, prepare uma pasta própria em cada servidor, por
exemplo `/opt/demeter`. A pasta deve conter `servidor.sh`, `docker-compose.prod.yml`,
`docker-compose.https.yml`, `docker-compose.unidade.yml`, `backend` e `frontend`.
Execute os comandos seguintes dentro dessa pasta. Há necessidade de acesso às
dependências/imagens durante a compilação pelo código; um pacote offline gerado
com as imagens dispensa essa etapa de download no destino.

## 5. Configurar o central

Disponibilize o certificado completo e a chave em uma pasta restrita da TI, por
exemplo `/etc/demeter/tls/servidor.pem` e `/etc/demeter/tls/chave.pem`. Certificado,
DNS e cadeia de confiança devem corresponder ao endereço informado.

```sh
chmod +x servidor.sh
./servidor.sh configurar --modo central \
  --endereco https://central.hospital.exemplo.local \
  --certificados /etc/demeter/tls
./servidor.sh validar
./servidor.sh iniciar
./servidor.sh status
```

Em uma instalação independente existente, use `--alterar` no comando configurar
para preservar as credenciais e o banco. Faça backup antes da atualização. A troca
para central não transfere automaticamente nenhuma unidade.

Na instalação nova, a senha temporária fica somente em
`work/credencial-inicial.txt`. Entre em `/login`, troque a senha e abra `/admin`.
Cadastre as unidades e confira dietas e formulários que serão copiados inicialmente.

Na atualização de um ambiente existente, mantenha seu volume PostgreSQL, `.env` e
configuração privada. Não importe um banco vazio sobre ele. A aplicação acrescenta
as estruturas do módulo ao iniciar. Não use comandos de remoção de volumes.

## 6. Cadastrar e preparar uma unidade

No central, entre como Administrador de TI e abra **Servidores das unidades**.

1. Escolha uma unidade ativa que ainda não possua servidor local.
2. Informe o endereço real do novo servidor local, sem `/admin` ou outro caminho.
3. Defina o intervalo de sincronização sem pendências; o padrão é 60 segundos,
   editável entre 15 e 3.600 segundos.
4. Clique em **Preparar e gerar vínculo**.
5. Baixe o vínculo privado e transfira-o por meio seguro para o servidor correto.

O arquivo contém a credencial de serviço daquela unidade. Não o envie por chat,
não o publique no GitHub e não o utilize em duas instalações. Se perder o arquivo,
renove o vínculo e instale a nova credencial preservando a identidade do servidor.

A preparação ainda não muda o atendimento. Congele brevemente os ajustes dos
cadastros durante a cópia inicial e confira-os no local antes da ativação.

## 7. Instalar o servidor da unidade

Use **uma base nova e vazia** para a unidade. Não copie o banco inteiro do central:
isso transportaria outras unidades, contas, códigos QR e filas de equipamentos.

Copie o vínculo para um local restrito. Quando a CA do central for interna, copie
também o certificado público dessa CA em PEM; a chave privada da CA não é necessária.

```sh
./servidor.sh configurar --modo unidade \
  --endereco https://havai.hospital.exemplo.local \
  --certificados /etc/demeter/tls \
  --vinculo /caminho-restrito/vinculo-havai.json \
  --ca-central /caminho-restrito/ca-central.pem
./servidor.sh validar
./servidor.sh iniciar
./servidor.sh status
```

Se o certificado do central já for confiável no sistema, omita `--ca-central`.
O vínculo será salvo em `work/unidade/vinculo.json`, com uma identidade exclusiva
desta instalação. O Compose monta essa pasta somente para leitura no backend.
O assistente não exibe seus segredos nem redefine senhas já existentes.

Na primeira conexão, o servidor importa nome/código da unidade, dietas,
formulários, prazos e configuração das impressoras. Usuários, senhas e segredos SMTP
não são copiados do central. Cadastros seguintes são administrados na unidade ou
enviados pela central com confirmação.

Entre com a credencial inicial **deste servidor**, troque a senha e crie os acessos
locais da equipe. Não crie uma segunda unidade nesta instalação.

## 8. Homologar antes de transferir o atendimento

O servidor local inicialmente está **Em preparação** e bloqueia novos pedidos.
Verifique a tela de servidores do central e a mesma aba no servidor da unidade.

- Confirme endereço, unidade, versão, contato recente e espaço disponível.
- Confira os dois formulários e as dietas/cardápios copiados.
- Cadastre usuários locais, perfis e vínculos; valide a troca obrigatória de senha.
- Configure SMTP e realize o teste sem usar destinatários de pacientes.
- Teste a conexão com as impressoras a partir do servidor da unidade.
- Confirme DNS e certificados em computador, celular e tablet da rede local.
- Valide o backup e a recuperação em ambiente isolado, mantendo a cópia desativada.

O AD continua sendo uma autenticação de rede: se o controlador de domínio não
estiver alcançável, um novo login AD pode falhar. Para continuidade, providencie
contas locais autorizadas para a operação e mantenha um administrador local ativo.
O módulo não armazena a senha do AD nem simula autenticação do domínio offline.

## 9. Ativar a operação local

Planeje uma janela curta com a Nutrição para transferir uma unidade por vez.

1. Suspenda novos envios dessa unidade pelos atalhos antigos.
2. Finalize ou cancele com justificativa os pedidos em andamento no central.
3. Confira filas de impressão e avisos de e-mail. Resolva trabalhos pendentes ou
   processando; confira fisicamente envios incertos antes de qualquer reimpressão.
4. No central, escolha **Ativar operação local**, leia a transferência e informe o motivo.
5. Aguarde a tela do servidor local indicar **Operação local ativada**.
6. Distribua os novos atalhos e reabra as solicitações no endereço local.

A ativação é recusada se houver pedidos pendentes/em preparo/prontos ou filas
pendentes/processando no central. A verificação e o bloqueio de escrita são
transacionais para evitar uma entrada simultânea durante a transferência.

Os dados históricos do central continuam disponíveis. Filipetas e QR Codes antigos
continuam pertencendo ao endereço onde foram gerados; conserve esse endereço para
consulta. Novas filipetas devem apontar para o servidor local configurado.

## 10. Homologar o ciclo completo após a ativação

Crie solicitações claramente identificadas como teste e siga o fluxo com a equipe.

1. Envie uma solicitação de Enfermagem e outra de Médico/Administração.
2. Confira o aparecimento no painel da cozinha local, sem login.
3. Confira a filipeta, acentos, nome da unidade e o pequeno QR Code.
4. Avance preparo/pronto e confira a impressão da etiqueta somente na etapa correta.
5. Confira o aviso médico no SMTP e no destinatário de teste.
6. Preencha o comprovante manual, escaneie o QR Code e entre com usuário local da Nutrição.
7. Registre recebedor, data/hora e foto legível da filipeta. A foto é otimizada para
   JPEG com até 2.000 pixels no maior lado e até 300 KiB, sem metadados EXIF.
8. Confira status, horário informado, horário do lançamento e responsável no relatório local.
9. Aguarde a publicação e confira o relatório consolidado no central, inclusive a foto.
10. Exporte XLSX, ODS e CSV e confira os mesmos filtros e totais. No Sheets, importe o CSV.

O relatório da rede utiliza identificadores globais. Dois pedidos de unidades
diferentes podem ter o mesmo número local sem serem o mesmo pedido.

## 11. Testar a perda de conexão

Em homologação, com autorização da rede, interrompa apenas a comunicação **entre a
unidade e o central**. Preserve a LAN, banco local, DNS necessário e impressoras.

Envie pedidos, avance as etapas, imprima e registre a entrega. A aplicação deve
continuar funcionando localmente, e os pedidos aguardando envio devem aumentar.
Restaure a comunicação e confira a redução da fila até zero, os totais e a ausência
de duplicatas. Uma perda de resposta pode produzir reenvio; o central confirma a
mesma publicação sem repetir impressões ou avisos médicos.

O SMTP externo depende de sua própria conectividade. Uma queda que também corte o
acesso ao provedor de e-mail pode adiar os avisos. Isso não impede registrar pedidos
nem usar a cozinha e a impressora alcançável na rede local.

## 12. Acompanhar a rede

No central, a aba **Servidores das unidades** mostra contato, última publicação,
versão informada, espaço livre, pedidos pendentes, divergências e fotos pendentes.
Os indicadores correspondem ao último contato recebido, não a uma leitura ao vivo
de uma unidade desconectada. Espaço livre é o disco visto pelo serviço da aplicação;
monitore também, na infraestrutura, o volume real do PostgreSQL e os backups.

Sem pendências, o agente usa o intervalo cadastrado com pequena variação para
evitar disparos simultâneos. Com dados para enviar, trabalha em lotes de até 20
pedidos e 2 MiB. Fotos são transferidas separadamente e verificadas por SHA-256.
Falhas aumentam o intervalo de nova tentativa, até aproximadamente cinco minutos.

A reconciliação percorre o inventário periodicamente e quando reconhece um novo
processo central. Ela pode repor registros ausentes após recuperação do central.
Relatórios centrais devem sempre ser interpretados conforme a última sincronização.

No servidor local, **Agendar nova tentativa** libera a próxima tentativa da fila.
O botão conserva as verificações de integridade e não força estados divergentes.

## 13. Backup e recuperação

**A consolidação central não substitui o backup completo da unidade.** Ela não
contém senhas, segredos SMTP, bytes das filas de impressão nem capacidades de QR
Code suficientes para reconstruir automaticamente toda a operação local.

Proteja e restaure em conjunto:

- Banco completo da instalação, incluindo identidades globais, histórico de
  publicações, eventos pendentes e recibos dos cadastros remotos.
- `.env`, `work/servidor.env`, `work/unidade/vinculo.json` e CA quando existente.
- Certificados/chaves TLS e configuração de infraestrutura em armazenamento restrito.
- Versão da aplicação correspondente ao backup e procedimento de atualização.

Mantenha cópia criptografada fora do servidor. Defina retenção, frequência e perda
máxima tolerável de dados com a TI. Para um RPO menor que o intervalo dos dumps,
avalie arquivamento de WAL/PITR ou snapshots consistentes do PostgreSQL.

Use o procedimento de [Monitoramento e recuperação](MONITORAMENTO-E-RECUPERACAO.md)
para conferir o backup em banco descartável. A cópia de teste não deve iniciar a
API, sincronização, impressão ou SMTP com a identidade da instalação real.

Em falha do servidor local:

1. Pare e isole a instalação anterior. Garanta que ela não volte a atender usuários.
2. Restaure banco e arquivos privados no substituto, mantendo uma única cópia ativa.
3. Preserve a identidade da instalação e o endereço usado nos QR Codes/atalhos.
4. Inicie a versão compatível, confira a operação local e depois a sincronização.
5. Se aparecer divergência de restauração, preserve ambos os bancos e interrompa
   a tentativa de unificação manual. Compare os registros/UUIDs com a TI antes de reconciliar.

Um backup antigo da unidade pode não conter dados já aceitos pelo central.
O agente detecta estados centrais ausentes no histórico de envios local e mantém
esses pedidos pendentes para análise. Não apague filas ou históricos para contornar
o aviso. Essa proteção não recupera registros nunca salvos em backup nem publicados.

## 14. Renovar ou revogar um vínculo

Somente a TI pode renovar/revogar a credencial, sempre com motivo. Renovar gera
outro arquivo privado e invalida o segredo anterior. No servidor correto, execute:

```sh
./servidor.sh configurar --modo unidade --alterar \
  --endereco https://havai.hospital.exemplo.local \
  --vinculo /caminho-restrito/novo-vinculo-havai.json
./servidor.sh iniciar
```

O assistente preserva `instalacao_uuid` já existente. Se o banco e o arquivo privado
discordarem sobre a instalação/unidade, o serviço recusa iniciar dessa forma.

Revogar interrompe a autorização para sincronizar. **Não paralisa o atendimento
local já ativado nem devolve a escrita ao central.** Para descomissionar um servidor,
planeje uma migração com parada explícita; não execute duas cópias ativas do mesmo
banco, mesmo com IPs diferentes. A clonagem integral também clona a identidade.

## 15. Atualização e expansão

Comece pela unidade Havaí, após homologação. Acompanhe atendimento, impressões,
entregas, cadastros e recuperação durante o piloto antes de replicar o procedimento
nas demais unidades. Não há instalação automática nem acesso remoto criado por este módulo.

Mantenha a mesma versão compatível nos servidores. Atualize primeiro uma cópia de
homologação; depois o central e uma unidade piloto; expanda em lotes acompanhados.
Faça backup antes de cada atualização e preserve os arquivos privados e volumes.
O protocolo atual é versão 1; incompatibilidades não devem ser contornadas apagando dados.

Instalações com interrupção podem continuar com uma versão diferente por um período,
mas a TI precisa confirmar a compatibilidade antes de misturar versões. O painel
informa versões; ele não instala atualizações nem executa comandos no sistema operacional.

## 16. Diagnóstico rápido

| Situação | Verificação / ação |
| --- | --- |
| Unidade em preparação | Confira primeiro contato, vínculo e ativação no central. |
| Erro de certificado | Confira DNS, validade/cadeia, relógio e CA. Não desative a validação TLS. |
| HTTP 401 na sincronização | Vínculo revogado/renovado ou segredo incorreto. Instale o arquivo correto. |
| HTTP 409 na sincronização | Confira identidade, ativação, versão e possível recuperação de banco antigo. |
| Pedidos locais normais, central atrasado | Confira enlace e fila; o atendimento local pode continuar após ativação. |
| Foto pendente | Confira conexão, pendências e existência do comprovante no servidor de origem. |
| Cadastro em revisão | Atualize a versão, compare com a unidade e envie nova proposta. |
| Impressão falhou | Teste a impressora a partir da unidade, IP/porta e fila. A sincronização não imprime no central. |
| Dois servidores para a mesma unidade | Isole a cópia indevida e preserve os bancos; não una automaticamente. |

Comandos de consulta no servidor:

```sh
./servidor.sh status
./servidor.sh logs backend
./servidor.sh logs frontend
```

## 17. Critério de liberação

Registre a unidade, responsáveis da TI e Nutrição, versão, endereços e data da
homologação. Libere somente após concluir login/perfis, dois formulários, cozinha,
filipetas/etiquetas, SMTP quando usado, QR/foto, relatório/exportação, queda e retorno
do enlace e recuperação de backup em ambiente isolado.

Este módulo fornece continuidade frente à indisponibilidade do enlace com o
central. Disponibilidade de energia, hardware, banco, rede local, impressoras e
capacidade de recuperação precisa ser mantida pela infraestrutura de cada unidade.
