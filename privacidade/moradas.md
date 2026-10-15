# Inventário de moradas · cliente 5

A cliente 5 pediu a eliminação dos dados (ela foi excluída da origem no dia 2; o pedido 106 permanece).
Cada linha é um lugar onde ela ainda pode viver, a técnica escolhida e o porquê. O comando é
`python3 lab.py esquecer 5`; a evidência é `privacidade/lista_eliminacao.json`.

| Morada | O que há da titular | Técnica | Por quê |
|---|---|---|---|
| origem · clientes | o cadastro (nome, e-mail, CPF, nascimento, cidade); já excluído pelo DELETE do dia 2 | apagar (DELETE) | o cadastro só existe para a relação com a cliente. O DELETE viaja pelo log até a bronze |
| origem · pedidos.observacao | o telefone escrito pelo atendimento no pedido 106 | limpar o campo (UPDATE para vazio) | o telefone é o dado pessoal em si, não há o que desvincular; o pedido e o valor ficam (nota fiscal, LGPD art. 16, I) |
| origem · navegacao | 2 eventos (5 e 8) com o IP dela | apagar (DELETE) | o IP identifica o aparelho dela e os eventos contam o que ela olhou |
| log · tópicos `mudancas` e `navegacao` | cargas dos eventos dela; a exclusão por chave | **lápide por chave + compactação**: um evento sem carga com a chave, e a carga dos eventos antigos dessa chave é zerada | o log só se anexa e não se edita; a exclusão fica registrada por chave e a compactação leva o conteúdo. Os offsets dos leitores continuam válidos |
| estado dos leitores do log | os eventos dela nas contagens de `por_cliente` e de `visitas` | apagar do estado | o que o leitor guardou por cliente é uma cópia derivada |
| camada bronze | cadastro (já removido pelo CDC), eventos de navegação, observação do pedido 106 | apagar + limpar + **crypto-shredding**: a chave do titular é apagada | tudo o que foi cifrado com a chave dela vira ruído, em qualquer cópia |
| camada silver | o pseudônimo dela nos pedidos e nos eventos | reconstruir sem ela; o pedido 106 fica com `cliente_ps` vazio | a silver é derivada; a lista de eliminação anula o pseudônimo, então o pedido fica "sem pessoa" e a receita continua |
| cópia de segurança | a bronze do dia 1 inteira, com o cadastro dela cifrado | **deixar expirar e não restaurar** o eliminado; como o cadastro está cifrado com a chave dela, apagar a chave também o torna ilegível | abrir e editar uma cópia é inviável (e impossível na imutável). Depois de cada restauração a lista de eliminação é reaplicada |
| saídas e evidências do pipeline | nada em claro | geradas sem dado pessoal; a verificação procura o nome, o CPF, o e-mail, o telefone e o IP dela em todos os documentos e saídas | evidência com dado pessoal seria uma morada nova |
| dados de partida do laboratório (`dados/dia1`) | o cadastro fictício dela | fora do pipeline: são os arquivos de carga fictícios da disciplina | em produção seriam o dump ou arquivo de carga, e entrariam nesta tabela |

Quatro técnicas para uma pessoa só: apagar, lápide com compactação, desvincular e deixar expirar, mais o
crypto-shredding por cima de tudo o que está cifrado.
