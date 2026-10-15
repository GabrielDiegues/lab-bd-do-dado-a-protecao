"""Camada silver: validada e protegida. Sem nome, e-mail, CPF, observacao nem ip; o mesmo pseudônimo
(cliente_ps) nas três tabelas, para a junção funcionar. Nada passa da bronze sem cumprir o contrato."""
import comum
from ingestao import bronze
from privacidade import eliminacao
from qualidade import validador
from seguranca import pseudonimo

DATA_REFERENCIA = "2026-10-03"  # data fixa: a idade (e a faixa) não muda de uma execução para outra
FAIXAS = [(25, 34, "25–34"), (35, 44, "35–44"), (45, 54, "45–54")]


def faixa_etaria(nascimento, ref=DATA_REFERENCIA):
    n, r = [int(x) for x in nascimento.split("-")], [int(x) for x in ref.split("-")]
    idade = r[0] - n[0] - ((r[1], r[2]) < (n[1], n[2]))
    for lo, hi, nome in FAIXAS:
        if lo <= idade <= hi:
            return nome
    return "até 24" if idade < 25 else "55 ou mais"


ESQUEMA_COM_DATA = """
CREATE TABLE clientes (cliente_ps TEXT PRIMARY KEY, nascimento TEXT, cidade TEXT);
"""
ESQUEMA_COM_FAIXA = """
CREATE TABLE clientes (cliente_ps TEXT PRIMARY KEY, faixa_etaria TEXT, cidade TEXT);
"""
ESQUEMA = """
CREATE TABLE pedidos (id INTEGER PRIMARY KEY, cliente_ps TEXT, valor_centavos INTEGER, status TEXT, criado_em TEXT);
CREATE TABLE navegacao (evento_id INTEGER PRIMARY KEY, cliente_ps TEXT, pagina TEXT, quando TEXT);
"""


def construir(generalizar=True, chave=None):
    """Apaga e recria a silver a partir da bronze. Devolve os números da construção."""
    k = chave or pseudonimo.chave()
    eliminados = eliminacao.chaves_eliminadas()

    def ps(cid):
        if cid is None or int(cid) in eliminados:
            return None
        return pseudonimo.pseudonimo(cid, k)

    br = bronze.abrir()
    (cli_ok, cli_rep), (nav_ok, nav_rep) = validador.validar_clientes_navegacao()
    ped_ok, ped_rep = validador.validar_pedidos(registrar=True)

    comum.apagar_banco("silver")
    sv = comum.conectar("silver")
    sv.executescript((ESQUEMA_COM_FAIXA if generalizar else ESQUEMA_COM_DATA) + ESQUEMA)
    for c in cli_ok:
        if int(c["id"]) in eliminados:
            continue
        if generalizar:
            sv.execute("INSERT INTO clientes VALUES (?,?,?)", (ps(c["id"]), faixa_etaria(c["nascimento"]), c["cidade"]))
        else:
            sv.execute("INSERT INTO clientes VALUES (?,?,?)", (ps(c["id"]), c["nascimento"], c["cidade"]))
    for p in ped_ok:
        sv.execute("INSERT INTO pedidos VALUES (?,?,?,?,?)",
                   (p["id"], ps(p["cliente_id"]), p["valor_centavos"], p["status"], p["criado_em"]))
    for n in nav_ok:
        sv.execute("INSERT INTO navegacao VALUES (?,?,?,?)", (n["evento_id"], ps(n["cliente_id"]), n["pagina"], n["quando"]))
    sv.commit()
    out = {
        "clientes": sv.execute("SELECT COUNT(*) FROM clientes").fetchone()[0],
        "pedidos": sv.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0],
        "navegacao": sv.execute("SELECT COUNT(*) FROM navegacao").fetchone()[0],
        "receita_paga": sv.execute("SELECT COALESCE(SUM(valor_centavos),0) FROM pedidos WHERE status='pago'").fetchone()[0],
        "em_quarentena": len(ped_rep) + len(cli_rep) + len(nav_rep),
    }
    sv.close()
    br.close()
    return out
