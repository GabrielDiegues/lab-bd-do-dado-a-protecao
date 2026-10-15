# Matriz classe × proteção

Cada linha soma à anterior. As classes usadas no acordo (`governanca/acordo.yaml`) são **pessoal** (os três
conjuntos) e, dentro dos contratos, também interno e confidencial. **Pessoal sensível** não ocorre na loja
(sem saúde, biometria, convicção etc.); o CPF recebe, mesmo assim, o tratamento mais forte do que a classe
exige, porque é o campo que mais dano faz se vazar.

| Classe | Proteção exigida | Como o laboratório executa | Estado |
|---|---|---|---|
| público / interno | cifra em trânsito e em repouso (o piso universal) | disco do host cifrado (LUKS/FileVault) e, em produção, TLS em toda seta; o laboratório roda em uma máquina só, então a cifra de trânsito é só documentada | piso documentado |
| confidencial (`valor_centavos`) | + controle de acesso fino, máscara para papéis amplos, trilha de leitura | papéis em `seguranca/acesso.py` (o analista só abre a silver e a gold, somente leitura) e trilha em `estado/auditoria.log` (inclui o acesso negado) | executado |
| pessoal (`cliente_id`, nome, e-mail, CPF, nascimento, cidade, IP, observação) | + máscara por padrão, token ou pseudônimo no pipeline, retenção executada | `cliente_ps = HMAC-SHA-256(CHAVE_PSEUDONIMO, id)` na silver; nome, e-mail, CPF, observação e IP não saem da bronze; nascimento vira faixa etária; o consumo recebe só agregado com K ≥ 2; retenção definida no acordo | executado; o **expurgo automático** pelo prazo do acordo é uma evolução, ainda não é um job |
| pessoal sensível | + criptografia de coluna, acesso por exceção auditada, cofre de reversão | **extra ligado:** o cadastro na bronze é cifrado por titular (AES-GCM, uma chave por cliente em `chaves_titular`); a chave é o cofre de reversão e apagá-la é o esquecimento | executado para o cadastro (aplicado ao CPF como se fosse sensível) |
| em todas | varredura do que escapou do mapa; teste sempre sintético ou mascarado | `governanca/varredor.py` (e-mail, telefone, CPF e IP em todas as colunas da bronze) e `dados/sintetico/` (pipeline inteiro rodando sem pessoa real) | executado |

## Papéis

| Papel | Camadas | Como é imposto |
|---|---|---|
| pipeline | lê a origem; lê e escreve bronze, silver e gold | código do pipeline (`seguranca/acesso.py`) |
| analista | lê **só** silver e gold, somente leitura | `acesso.abrir("analista", camada)` abre o banco com `mode=ro` e nega a bronze |

Em produção o mesmo desenho vira dois usuários do sistema de arquivos ou do banco: o grupo `pipeline` com
permissão de escrita nos arquivos da bronze e o grupo `analistas` apenas com `chmod 640` na silver e na gold,
sem nenhuma permissão na bronze.

## A chave

`CHAVE_PSEUDONIMO` vem da variável de ambiente, nunca do código nem do repositório. Uma cópia fica no cofre,
**fora** da pasta do repositório (`../cofre-lab-bd/chave_pseudonimo.txt`, modo 0600), porque sem ela uma
restauração gera pseudônimos que não ligam com nada. A verificação procura o valor da chave em todo o
repositório e deve achar zero ocorrências.
