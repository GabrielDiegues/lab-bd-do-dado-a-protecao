# Plano de resiliência

Falha, ataque ou dedo nervoso: o dado volta. Os números abaixo são **decisão de negócio** e foram pensados
para a loja; o ensaio (`python3 lab.py ensaio`) mede o RTO real e compara com a promessa.

| Sistema | RPO | RTO | Cópias (onde · como · por quanto tempo) | Responsável |
|---|---|---|---|---|
| origem | 15 min | 1 h | snapshot local a cada 15 min (24 h) · cópia noturna em outro armazenamento (35 dias) · cópia semanal isolada e imutável (35 dias) | time de Plataforma de Dados |
| log de mudanças | 15 min | 1 h | vive na origem, entra nas mesmas cópias; o tópico `navegacao` tem retenção curta (7 dias) e é reproduzível pela origem | time de Plataforma de Dados |
| camada bronze | 24 h | 2 h | cópia diária em outra pasta/armazenamento (35 dias) · cópia isolada imutável semanal (35 dias) · reaplicar o log desde o offset guardado fecha o resto | time de Plataforma de Dados |
| camada silver | — | 30 min | reconstruída a partir da camada bronze (`lab.py reconstruir`); não é copiada | time de Plataforma de Dados |
| chave | 0 | 15 min | cofre principal · cópia no cofre separado, fora do ambiente de produção, em outro provedor (sem prazo, só rotação) · inclui `CHAVE_PSEUDONIMO` e as chaves por titular | time de Segurança da Informação |

## 3-2-1-1-0 do grupo

**3 cópias · 2 locais · 1 fora · 1 imutável · 0 erros no teste.**

| # | Cópia | Local | No laboratório | Em produção |
|---|---|---|---|---|
| 1 | a bronze viva | produção | `estado/bronze.db` | armazenamento da produção |
| 2 | cópia diária | outro local (fora do repositório) | `../backup-lab-bd/<nome>/` | outro armazenamento, mesma conta de operação |
| 3 | cópia **isolada e imutável** | "fora do site" | `../cofre-lab-bd/copia_isolada/<nome>/` somente leitura (0444, pasta 0555) | outro provedor, credencial e agenda independentes, trava de retenção de 30 dias |

**Qual cópia é imutável? Qual fica isolada, com credencial independente?** A cópia 3 é as duas coisas: somente
leitura e fora do caminho de quem opera a produção. A cópia 2 está no mesmo domínio de credencial da operação;
sozinha, não sobreviveria a um invasor com credencial de administrador. No laboratório a imutabilidade é
`chmod`; em produção seria uma trava de objeto (o ataque que cifra a produção e apaga o que alcança não alcança
uma cópia travada por 30 dias, que cobre as duas semanas em que alguém poderia ter desligado a agenda).

0 erros: toda cópia carrega um manifesto com SHA-256 e a restauração só segue se os hashes e o
`PRAGMA integrity_check` baterem (`resiliencia/backup.py`).

## Ordem de restauração

1. **Chaves** (`CHAVE_PSEUDONIMO` e o cofre de chaves por titular). Dado restaurado sem chave é lixo cifrado.
2. **Dados**: a bronze da cópia, com os offsets guardados junto.
3. **Log**: reaplicar o que veio depois do offset (mudanças e navegação).
4. **A lista de eliminação**, sempre: o eliminado não volta. Isto também apaga a chave dele, caso a cópia do cofre a
   tenha trazido de volta.
5. **O lote que chegou depois** (dia 3).
6. **Silver e gold**: `lab.py reconstruir`.
7. **Validação**: os números do ensaio (6 clientes, 11 pedidos, 6 eventos, R$ 844,90, mesma visão de consumo).

## O ensaio

`python3 lab.py ensaio` apaga a bronze, restaura a cópia do dia 1 (que ainda contém a cliente 5), reaplica o log,
a lista de eliminação e o lote do dia 3, e reconstrói. O tempo é o RTO real. O resultado fica em
`evidencias/missao9.txt`, com a diferença para a promessa acima.
