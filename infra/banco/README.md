# Estrutura limpa do Deméter 0.1.1

`demeter-banco-limpo-0.1.1.sql` contém somente a estrutura PostgreSQL 16: tabelas,
índices, restrições e sequências. Não contém registros, contas, senhas, pacientes,
pedidos, fotos, configuração SMTP ou impressoras.

O instalador Linux prepara a estrutura automaticamente. Esse SQL é uma alternativa
para a TI, exclusivamente em um banco novo vazio. Não importe sobre uma base em uso.

```sh
psql --dbname=NOVO_BANCO --set=ON_ERROR_STOP=1 --file=demeter-banco-limpo-0.1.1.sql
```

Configure o endereço desse banco e os segredos da nova instalação antes de iniciar
a aplicação. No primeiro início, o Deméter cria os quatro perfis e o administrador
com senha temporária; a troca é obrigatória no primeiro acesso. Veja
[Produção limpa](../../PRODUCAO-LIMPA.md).

O esquema foi exportado com PostgreSQL 16.15; o cliente `psql` dessa versão foi
usado na importação de validação. O esquema foi restaurado em outro banco
vazio e conferido: todas as tabelas sem registros. Os dados da instalação atual
não participam dessa exportação.
