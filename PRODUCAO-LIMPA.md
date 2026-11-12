# Deméter — banco novo para produção

A versão 0.1.1 inicializa um banco novo com a estrutura da aplicação, quatro
perfis de acesso e um administrador de TI com senha temporária exclusiva.
Não cria unidades, dietas, cardápios, formulários de unidade, impressoras,
pedidos, pacientes, entregas ou registros de demonstração.

## Instalar

Use o novo `demeter-0.1.1-linux-amd64.run` em uma instalação nova, conforme
[Distribuição Linux](DISTRIBUICAO-LINUX.md). O instalador cria outro volume/banco;
o banco da estação atual não é copiado, apagado ou modificado. Ele também recusa
substituir uma instalação ou volume `demeter` já existente.

O banco é preparado automaticamente na primeira execução. Não é necessário
importar o SQL separado quando se usa o instalador.

## Primeiro acesso

1. Consulte `work/credencial-inicial.txt` no servidor para a conta `admin`.
2. Troque a senha temporária no primeiro login.
3. Em Administração → Unidades, crie a primeira unidade. Nesse momento são criados
   os dois formulários iniciais dessa unidade, ainda sem catálogo de dietas copiado.
4. Configure dietas/cardápios, impressoras e as contas/perfis de cada equipe.
5. Baixe os atalhos das unidades e conclua a homologação da instalação.

Enquanto nenhuma unidade foi cadastrada, reiniciar a aplicação mantém o mesmo
administrador e a mesma senha escolhida. A aplicação não recria a conta nem insere
unidades ou dietas de exemplo na próxima inicialização.

## Esquema SQL separado

[demeter-banco-limpo-0.1.1.sql](infra/banco/demeter-banco-limpo-0.1.1.sql) é um esquema PostgreSQL 16 exportado de um banco
novo descartável, contendo tabelas, índices, restrições e sequências, sem dados.
Não contém usuários/senhas do PostgreSQL, conta administrativa, pacientes ou pedidos.
Destina-se somente a um banco novo vazio preparado pela TI, como alternativa técnica.
O primeiro início da aplicação depois da importação cria os perfis e o administrador
a partir da configuração privada dessa instalação. Não aplique sobre o banco em uso.

A conferência de produção inclui a restauração desse SQL em outro banco vazio e
a contagem de todas as tabelas. O ambiente descartável é removido ao fim do teste.
Os arquivos `.sha256` permitem conferir a integridade da transferência.

## Bases existentes e demonstração

Esta mudança não contém instruções de limpeza, exclusão ou redefinição de dados
existentes. Contas e cadastros já presentes são preservados. A demonstração somente
é criada se `INICIALIZAR_DEMONSTRACAO=true` for configurada explicitamente em
desenvolvimento; produção fixa essa opção como falsa e rejeita sua ativação.
