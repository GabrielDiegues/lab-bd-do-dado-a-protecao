# O trajeto do CPF neste pipeline

Em cada etapa o CPF está **real**, em **token**, **mascarado**, **ausente** ou **sintético**.

| # | Etapa | Forma do CPF | Por quê |
|---|---|---|---|
| 1 | Cadastro na origem | real | é onde o dado nasce e a nota fiscal precisa dele; disco cifrado e acesso restrito |
| 2 | Log de mudanças (`origem.mudancas`) | **real (ponto de atenção)** | na Trilha A o gatilho grava a linha inteira do cadastro no evento. É uma morada a mais do CPF: só se justifica com retenção curta, e o `esquecer` zera a carga útil do titular. Evolução possível: evento magro, sem o CPF |
| 3 | Camada bronze | **cifrado com a chave do titular** (AES-GCM) | cópia fiel e restrita ao pipeline; sem a chave do titular o valor é ruído. O CPF "em claro" só existe na memória do pipeline |
| 4 | Camada silver | ausente | o analista lê esta camada; nenhuma análise usa o CPF. O que liga o cliente aos pedidos é o `cliente_ps` |
| 5 | Visão de consumo (gold) | ausente | o consumo recebe agregado por cidade com K ≥ 2 |
| 6 | Ambiente de teste | sintético | `dados/sintetico/`: mesma forma, nenhuma pessoa real (CPFs do tipo `000.000.001-00`) |

Resumo: o CPF real vive na **origem** e, por necessidade técnica da Trilha A, nos eventos do **log**
(protegidos por retenção curta e por lápide). Na bronze já está cifrado; da silver em diante, não existe.
