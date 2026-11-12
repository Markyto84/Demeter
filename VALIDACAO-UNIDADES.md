# Validação do módulo de unidades - Deméter 0.2.0

Revisão realizada em 12/11/2026, com dados fictícios e recursos isolados.
Nenhuma instalação hospitalar foi transferida ou teve o banco zerado.

## Resultados

- Backend: 391 testes, sendo 390 aprovados e 1 dependente de Caddy externo omitido.
- Frontend: 88 testes aprovados e compilação de produção concluída.
- PostgreSQL: captura transacional, rollback, confirmação por eventos efetivamente
  lidos, ordem de commit diferente da ordem das sequências e ativação concorrente.
- Integridade: perda da resposta/reenvio sem duplicação; identificação global de
  pedidos com números locais iguais; proteção contra restauração local divergente;
  reconciliação de registros ausentes no central.
- Autorização: vínculo de instalação exclusivo, revogação do serviço e restrições
  por unidade para relatórios, cadastros e comprovantes.
- Gestão compartilhada: criação/alteração pela central com recibo; detecção de
  conflito com alteração local; senha temporária de nova conta e ausência de hashes
  de usuários na consolidação.
- Fotos: transporte separado, conferência de integridade, reenvio e deduplicação.
- Instalação limpa: SQL restaurado em banco descartável, com 33 tabelas sem
  registros e os 24 gatilhos de captura/proteção instalados.
- Dependências: nenhuma vulnerabilidade conhecida identificada nas dependências
  Python da imagem Linux e nas dependências npm de produção, na data da revisão.

## Exercício Linux com perda do enlace

Foram iniciadas três aplicações Linux em contêineres, com três bancos PostgreSQL:
uma central e duas unidades. As unidades validaram o HTTPS do central com uma CA
exclusiva de homologação. A comunicação entre unidades e central foi interrompida,
mantendo disponíveis os bancos e o acesso local.

| Verificação | Resultado |
| --- | --- |
| Solicitações durante a interrupção | 6 registradas nas unidades |
| Avanços de etapa sem central | 12 alterações concluídas |
| Entrega com horário, recebedor e foto sem central | 1 comprovante registrado |
| Retorno do enlace | Sincronização automática concluída |
| Duplicatas na consolidação | 0 |
| Pedidos/filas operacionais criados pelo recebimento no central | 0 |
| Totais consolidados | 6 solicitações; 1 entregue; 5 prontas |
| Arquivos exportados | XLSX, ODS e CSV |
| Cadastro enviado pela central | Aplicado e confirmado pela unidade |
| Interface | Painel, formulário remoto, relatório, foto e histórico conferidos no navegador |

Nesse exercício, a retomada levou aproximadamente 19 segundos após a reconexão.
Esse tempo reflete o momento da tentativa automática em um laboratório pequeno;
não representa SLA, teste de carga das 21 unidades ou estimativa para todos os enlaces.

O teste não enviou papel para impressoras reais nem e-mail hospitalar. A verificação
física dos equipamentos, DNS, certificados nos dispositivos, SMTP, contas AD,
backup e recuperação de cada instalação continua no roteiro de homologação da TI.

## Materiais para implantação

- [Manual operacional e de instalação](IMPLEMENTACAO-UNIDADES.md).
- [Manual em PDF](output/pdf/Manual-implantacao-unidades-Demeter.pdf).
- [Esquema SQL sem registros](infra/banco/demeter-banco-limpo-0.2.0.sql).

A instalação independente permanece como padrão. A ativação local depende da
preparação do servidor, do vínculo privado e da transferência explícita pela TI.
