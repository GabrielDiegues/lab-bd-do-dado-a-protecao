# Do dado à proteção · laboratório de BD

**Grupo:** Gabriel Diegues Figueiredo Rocha (RM 550788)
**Linguagem e bancos:** Python 3.12 (stdlib + PyYAML + `cryptography`). Origem e todas as camadas em SQLite, um arquivo por camada em `estado/` (ignorado pelo git).
**Trilha de captura de mudanças:** **Trilha A**, sem infraestrutura. Uma tabela `mudancas` na própria origem, preenchida por gatilhos do banco (inserção, alteração e exclusão). Motivo: o log nasce na mesma transação da mudança, na ordem do commit, seja qual for o programa que a fez; roda em qualquer máquina e no Codespaces sem subir servidor. A exclusão leva só a chave. O custo está registrado abaixo (o CPF viaja no evento).

O projeto leva o dado de uma loja online do `INSERT` até um destino governado, protegido e restaurável: carga incremental, captura de mudanças, tópico com vários leitores, contrato e quarentena, governança, pseudonimização, visão de consumo com K-anonimato, direito de ser esquecido e ensaio de restauração.

## Como rodar do zero

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

# a chave do pseudônimo vem do ambiente; nunca do código nem do repositório
export CHAVE_PSEUDONIMO=$(python3 -c 'import secrets; print(secrets.token_hex(32))')

python3 lab.py tudo            # origem -> carga -> captura -> fluxo -> dia 2 -> CDC -> lote do dia 3 -> silver -> gold
python3 lab.py esquecer 5      # direito de ser esquecido (idempotente)
python3 lab.py reconstruir     # apaga e recria silver e gold a partir da bronze
python3 lab.py ensaio          # desastre cronometrado: restaura a cópia do dia 1 e confere
python3 lab.py verificar       # roda tudo e confere CADA número esperado das Missões 0 a 9
```

Comandos avulsos (um por peça): `origem-init`, `carga`, `dia2`, `captura`, `sincronizar [--do-zero]`, `fluxo [--tempo-real]`,
`leitor-novo`, `lote`, `validar`, `regras`, `catalogo`, `varredor`, `silver`, `gold --k N`, `proteger`, `backup`. `python3 lab.py -h` lista todos.

**Apresentação em sala:** `python3 lab.py tudo`, depois `python3 lab.py esquecer 5` e `python3 lab.py reconstruir`, e mostrar em `arquitetura/vida-do-dado.svg` por onde o dado dela passou.

Variáveis opcionais: `LAB_ESTADO` (pasta dos bancos), `LAB_BACKUP` e `LAB_COFRE` (cópias, **fora** do repositório; por padrão `../backup-lab-bd` e `../cofre-lab-bd`).
`verificar` apaga e recria o `estado/` e regrava `evidencias/`.

## Peças da entrega

| Semana | Missão | Peça | Onde está e qual número a comprova |
|---|---|---|---|
| 1 | 1 | Carga incremental | `ingestao/carga.py` (+ `ingestao/origem.py`, `ingestao/bronze.py`). 1ª execução 6/8/8; 2ª lê **0** linhas; depois do dia 2 lê **4** (105, 109, clientes 3 e 7); bronze 7 clientes, 9 pedidos, R$ 750,90. `evidencias/missao1.txt` |
| 1 | 2 | Log de mudanças | `ingestao/cdc.py` (gatilhos, tabela `mudancas`, offset). **5 eventos** em ordem; bronze com 6 clientes (sem a 5), 9 pedidos, e-mail novo da cliente 3, R$ 750,90; reaplicar o log dá os mesmos números. `evidencias/missao2.txt` |
| 2 | 3 | Fluxo com vários leitores | `ingestao/fluxo.py` (tópico `navegacao`; leitores `visitas`, `bronze`, `por_cliente`). `/carrinho` = 2 e as outras seis páginas = 1; bronze com 8 eventos sem duplicata; leitor novo relê do offset 0; o log fica com os 8 eventos. `evidencias/missao3.txt` |
| 2 | 4 | Contrato e quarentena | `contratos/*.yaml`, `qualidade/validador.py`. Do lote do dia 3, **2 aceitas** (110 e 115) e **5 em quarentena** com 5 motivos; silver com 11 pedidos e R$ 844,90 (sem a validação seria R$ 932,90). `evidencias/missao4.txt` |
| 3 | 5 | Acordo de governança | `governanca/acordo.yaml`, `catalogo.md` (gerado por `catalogo.py`), `regras.py` (a regra que barra o pipeline), `varredor.py`. Sem a retenção de `navegacao` o pipeline para; o varredor acha `observacao` (pedidos 104 e 106) e `ip` (8 eventos). `evidencias/missao5.txt` |
| 3 | 6 | Matriz e trajeto do CPF | `seguranca/matriz.md`, `trajeto_cpf.md`, `pseudonimo.py`, `silver.py`, `acesso.py`. Nenhuma ocorrência de e-mail/CPF/telefone/IP na silver; mesma chave, mesmos pseudônimos; outra chave, todos mudam; a chave não está no repositório. **Extra:** pipeline com `dados/sintetico/`. `evidencias/missao6.txt` |
| 4 | 7 | Visão de consumo | `privacidade/consumo.py`. K da tabela de clientes: **4** combinações com uma pessoa só; com K = 2, Santos R$ 545,00 (3), Sorocaba R$ 95,90 (2), Campinas suprimida; total R$ 844,90; K = 3 suprime Sorocaba. `evidencias/missao7.txt` |
| 4 | 8 | Esquecimento com evidência | `privacidade/moradas.md`, `esquecer.py`, `eliminacao.py`, `lista_eliminacao.json`. Nenhuma ocorrência da titular nas camadas (nem nos bytes dos arquivos); 6 eventos, 11 pedidos, R$ 844,90; a visão de consumo não muda; a lista tem 1 registro sem dado pessoal; rodar de novo não muda nada. **Extra:** crypto-shredding (`seguranca/cripto.py`). `evidencias/missao8.txt` |
| 5 | 9 | Plano de resiliência | `resiliencia/plano.md`, `backup.py`, `reconstruir.py`, `ensaio.py`. O ensaio restaura a cópia do dia 1 (com a cliente 5), reaplica log e lista de eliminação, carrega o lote do dia 3 e reconstrói: mesmos números da Missão 8. **Extra:** reconstruir com outra chave. `evidencias/missao9.txt` |
| 5 | 10 | Desenho e README | `arquitetura/estrutura.svg` e `arquitetura/vida-do-dado.svg`, fonte em `arquitetura/gerar_diagramas.py`; este README |

## Números finais

| Camada | Clientes | Pedidos | Eventos de navegação | Receita paga |
|---|---|---|---|---|
| origem (depois do esquecer) | 6 | 9 | 6 | R$ 750,90 |
| bronze (+ 7 linhas do lote do dia 3 em `pedidos_lote`) | 6 | 9 | 6 | R$ 750,90 |
| silver | 6 | 11 | 6 | **R$ 844,90** |

Visão de consumo (`gold.receita_por_cidade`, K = 2): Santos R$ 545,00 (3 clientes) · Sorocaba R$ 95,90 (2) · Campinas suprimida (1). Total geral R$ 844,90, que inclui a cidade suprimida e os R$ 159,00 do pedido 106, que não tem mais cadastro. Quarentena: 5 linhas, cada uma com o seu motivo.

## RTO medido no ensaio

O ensaio levou **cerca de 0,05 s** (cópia local e cópia isolada; ver `evidencias/missao9.txt`), contra **2 h** prometidas no plano para bronze + silver. A diferença enorme vem do tamanho do laboratório (25 linhas): o RTO real de produção só sai do mesmo ensaio, feito com o volume real. O que o laboratório prova é o método e a correção: a cópia do dia 1 contém a cliente 5, e depois de restaurar, reaplicar o log e a lista de eliminação ela não reaparece em nenhuma camada, com os mesmos números de antes do desastre.

## Decisões e limites (o que vale defender em sala)

- **Offset (Missão 3).** O leitor salva o offset **depois** de processar (entrega pelo menos uma vez) e processa de forma **idempotente** (`INSERT OR IGNORE` pela chave do evento). Cair entre processar e salvar repete um evento e **não o perde**, e repetir não conta duas vezes (cenário 3 de `evidencias/missao3.txt`). Salvar antes inverteria o risco: a queda perderia um evento.
- **CDC por gatilhos (Missão 2).** O evento de inserção e de alteração leva a linha inteira, **inclusive o CPF**. É uma morada a mais, aceita como ponto de atenção em `seguranca/trajeto_cpf.md`: o `esquecer` zera a carga útil do titular no log. A saída para uma plataforma de verdade é um evento magro, sem o CPF.
- **Dono mais difícil de defender: `navegacao`.** Quem mais usa é marketing; quem produz é o time de Produto e Experiência Digital; quem guarda o IP, por obrigação legal, é a engenharia. O dono é o time de Produto, porque é quem decide que evento existe e para quê, e a retenção de 6 meses nasce do uso (funil) e do Marco Civil (art. 15, registro de acesso). A engenharia é custodiante, não dona.
- **Pseudônimo não é anônimo.** Na LGPD (art. 13, § 4º) o dado pseudonimizado continua pessoal. Por isso o consumo recebe agregado, com limiar K, e a silver generaliza o nascimento em faixa etária.
- **Pedido 106 sem pessoa.** Depois do esquecimento, `cliente_ps` fica vazio e a observação é limpa; `cliente_id = 5` permanece na origem e na bronze como número órfão (o cadastro não existe mais). Se a sua leitura de "sem pessoa" exigir apagar também o número, é uma mudança de uma linha em `esquecer.py`, mas o contrato exige `cliente_id`.
- **Cópia imutável.** No laboratório, "imutável" é permissão somente leitura (`chmod`) e "fora do site" é outra pasta fora do repositório. Em produção seria uma trava de objeto em outro provedor, com credencial independente. O `plano.md` descreve os dois.
- **Cifra em repouso.** Os arquivos SQLite não são cifrados por si; o piso (disco cifrado) é documentado, e o cadastro na bronze é cifrado por titular (AES-GCM).
- **Retenção.** Os prazos estão no acordo e a regra como código exige que existam. O **expurgo automático** por prazo não foi implementado (só o esquecimento sob demanda).
- **Dados fictícios.** `dados/dia1` traz o cadastro fictício da disciplina (CPFs inválidos de propósito, IPs de documentação). A verificação procura os dados da titular em tudo o que o pipeline produz, mas não nesses arquivos de partida.

## Estrutura

```
pipeline/
├── dados/          dia 1, mudanças do dia 2, lote do dia 3, sintético
├── contratos/      pedidos.yaml, clientes.yaml, navegacao.yaml
├── ingestao/       origem, carga incremental, bronze, CDC, tópico e leitores
├── qualidade/      validação e quarentena
├── governanca/     acordo.yaml, catalogo.md, regras como código, varredor
├── seguranca/      matriz.md, pseudonimização, camada silver, papéis, crypto-shredding
├── privacidade/    visão de consumo, moradas.md, esquecer, lista de eliminação
├── resiliencia/    plano.md, cópia de segurança, reconstruir, ensaio
├── arquitetura/    fonte e imagem do desenho (estrutura e vida do dado)
├── evidencias/     números de cada missão (gerados por scripts/verificar.py)
├── scripts/        verificar.py, gerar_sintetico.py
└── lab.py          a CLI do pipeline
```
