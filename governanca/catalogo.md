# Catálogo de dados

_Gerado por `governanca/catalogo.py` a partir de `contratos/*.yaml` e `governanca/acordo.yaml`. Não edite à mão._

## clientes

Cadastro de quem compra na loja.

- **Dono:** time de Atendimento e Cadastro
- **Classe:** pessoal
- **Frescor:** até 24 horas depois da mudança na origem
- **Retenção:** enquanto durar a relação com a cliente. uso (atender e entregar). Ao pedido de eliminação (LGPD art. 18, VI) o cadastro é apagado; só fica o que a obrigação legal exige (art. 16, I), e isso mora nos pedidos.
- **Acesso:** pede qualquer time da loja, com a finalidade escrita; aprova dono do conjunto (time de Atendimento e Cadastro); audita toda leitura de CPF, e-mail ou nome por papel diferente do pipeline; revisão trimestral

| Campo | Tipo | Obrigatório | Classe | Descrição | Finalidade |
|---|---|---|---|---|---|
| `id` | inteiro | sim | pessoal | Identificador do cliente; leva à pessoa. | chave de junção (na camada silver vira o pseudônimo cliente_ps) |
| `nome` | texto | sim | pessoal | Nome completo. | — |
| `email` | texto | sim | pessoal | E-mail de contato. | — |
| `cpf` | texto | sim | pessoal | CPF, necessário para a nota fiscal. Real só na origem e na camada bronze. | — |
| `nascimento` | data | sim | pessoal | Data de nascimento. | segmentar por faixa etária (na silver só a faixa etária) |
| `cidade` | texto | sim | pessoal | Cidade do cadastro. | receita por cidade |
| `atualizado_em` | data_hora | sim | interno | Última alteração na origem; é a marca-d'água da carga incremental. | — |

## pedidos

Pedidos feitos na loja online, um por linha.

- **Dono:** time de Vendas
- **Classe:** pessoal
- **Frescor:** até 24 horas depois da mudança na origem
- **Retenção:** 5 anos. obrigação fiscal e prazo de prescrição tributária (LGPD art. 16, I); depois disso, eliminação ou anonimização
- **Acesso:** pede finanças, analistas e atendimento; aprova dono do conjunto (time de Vendas); audita leitura da coluna observacao e qualquer exportação fora da plataforma

| Campo | Tipo | Obrigatório | Classe | Descrição | Finalidade |
|---|---|---|---|---|---|
| `id` | inteiro | sim | interno | Identificador do pedido. | — |
| `cliente_id` | inteiro | sim | pessoal | Cliente que fez o pedido; é um número que leva à pessoa. | ligar o pedido ao cliente (na camada silver vira o pseudônimo cliente_ps) |
| `valor_centavos` | inteiro | sim | confidencial | Valor do pedido, em centavos. | — |
| `status` | texto | sim | interno | Situação do pedido. | — |
| `criado_em` | data_hora | sim | interno | Quando o pedido foi criado. | — |
| `observacao` | texto | não | pessoal | Recado do atendimento. Texto livre, não sai da camada bronze. | operar a entrega (não é necessária para a análise) |
| `atualizado_em` | data_hora | não | interno | Última alteração na origem; é a marca-d'água da carga incremental. | — |

## navegacao

Cliques e visitas às páginas da loja, um evento por linha.

- **Dono:** time de Produto e Experiência Digital
- **Classe:** pessoal
- **Frescor:** até 24 horas depois do evento (leitor rápido: segundos)
- **Retenção:** 6 meses. volume alto e uso curto (análise de funil); o IP, como registro de acesso, também tem prazo de 6 meses no Marco Civil (art. 15)
- **Acesso:** pede analistas de produto e marketing; aprova dono do conjunto (time de Produto e Experiência Digital); audita leitura da coluna ip e o cruzamento dela com cliente_id

| Campo | Tipo | Obrigatório | Classe | Descrição | Finalidade |
|---|---|---|---|---|---|
| `evento_id` | inteiro | sim | interno | Identificador do evento; impede a duplicata ao reler. | — |
| `cliente_id` | inteiro | não | pessoal | Cliente logado; vazio para visitante. | contar eventos por cliente (na camada silver vira o pseudônimo cliente_ps) |
| `ip` | texto | sim | pessoal | Endereço IP de quem navegou. Não sai da camada bronze. | registro de acesso exigido por lei (Marco Civil, art. 15); fora da análise |
| `pagina` | texto | sim | interno | Página visitada. | — |
| `quando` | data_hora | sim | interno | Momento do evento. | — |
