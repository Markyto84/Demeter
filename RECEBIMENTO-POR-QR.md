# Deméter — comprovação de entrega pelo QR Code

O fluxo vigente usa a **filipeta assinada no papel**, complementada pelo lançamento
autenticado da Nutrição. O QR Code pequeno no cabeçalho identifica o pedido; ele não
substitui o registro manual do recebimento na filipeta.

## Operação

1. A unidade solicita a refeição e a cozinha acompanha o preparo.
2. Na entrega, preencha no papel o nome do recebedor, a assinatura, a data e a hora.
3. A Nutrição escaneia o QR Code com celular ou tablet e entra com seu usuário.
4. Informe o recebedor e a data/hora efetiva da entrega e anexe a foto da filipeta assinada.
5. Ao confirmar, o servidor registra o comprovante e finaliza o pedido como entregue.

O painel de entregas das copeiras está desativado. Somente Nutricionista e
Administrador de TI, com acesso à unidade, registram o comprovante. O histórico
identifica quem recebeu, quem registrou, o horário informado da entrega e o horário
do lançamento no sistema. Uma confirmação repetida não gera outra entrega.

## Fotografia

O servidor aceita JPG, PNG e WebP, com até 12 MiB de entrada e 32 megapixels.
Remove metadados, corrige a orientação e guarda somente a versão JPEG em tons de
cinza, com lado máximo de 2000 pixels e até **300 KiB**. A imagem original não é
armazenada. Fotos pequenas demais ou sem compactação aceitável são recusadas, para
preservar a leitura do comprovante.

A foto e seus dados de integridade ficam no banco, vinculados ao pedido. A consulta
ao comprovante exige autenticação e permissão da unidade; o código público não
expõe os dados completos do paciente.

## Instalação e versões futuras

Configure o endereço público em `servidor.sh configurar` antes de emitir novas
filipetas. O celular deve conseguir acessar esse endereço na rede da unidade.
Homologue o QR Code e a captura da foto no servidor e nos dispositivos de destino.

O fluxo anterior de assinatura digital/identificação da copeira foi separado para
uma implementação futura. Reativá-lo exige homologação própria e decisão da gestão;
não representa o comportamento da versão atual. Registros históricos são preservados.
