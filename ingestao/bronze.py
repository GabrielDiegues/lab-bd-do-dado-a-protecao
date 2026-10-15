"""Camada bronze: cópia fiel da origem, mais colunas de controle (_carregado_em, _execucao)."""
import comum
from seguranca import cripto

ESQUEMA = """
CREATE TABLE IF NOT EXISTS clientes (
  id INTEGER PRIMARY KEY, nome TEXT, email TEXT, cpf TEXT, nascimento TEXT, cidade TEXT,
  atualizado_em TEXT, _carregado_em TEXT, _execucao INTEGER);
CREATE TABLE IF NOT EXISTS pedidos (
  id INTEGER PRIMARY KEY, cliente_id INTEGER, valor_centavos INTEGER, status TEXT,
  criado_em TEXT, atualizado_em TEXT, observacao TEXT, _carregado_em TEXT, _execucao INTEGER);
CREATE TABLE IF NOT EXISTS navegacao (
  evento_id INTEGER PRIMARY KEY, cliente_id INTEGER, ip TEXT, pagina TEXT, quando TEXT,
  _carregado_em TEXT, _execucao INTEGER);
-- lote de pedidos que chega por arquivo (dia 3): como chegou, inclusive duplicatas
CREATE TABLE IF NOT EXISTS pedidos_lote (
  arquivo TEXT, linha INTEGER, id INTEGER, cliente_id INTEGER, valor_centavos INTEGER, status TEXT,
  criado_em TEXT, observacao TEXT, _carregado_em TEXT, _execucao INTEGER, PRIMARY KEY (arquivo, linha));
CREATE TABLE IF NOT EXISTS marca_dagua (tabela TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS execucoes (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, iniciada_em TEXT);
CREATE TABLE IF NOT EXISTS quarentena (
  conjunto TEXT, origem TEXT, linha INTEGER, conteudo TEXT, motivo TEXT, execucao INTEGER, em TEXT,
  PRIMARY KEY (conjunto, origem, linha));
"""


def abrir():
    con = comum.conectar("bronze")
    con.executescript(ESQUEMA)
    return con


def nova_execucao(con, tipo):
    cur = con.execute("INSERT INTO execucoes (tipo, iniciada_em) VALUES (?, ?)", (tipo, comum.agora()))
    return cur.lastrowid


def gravar_cliente(con, r, exe):
    """Mescla pela chave id. Com crypto-shredding ativo, os campos pessoais entram cifrados."""
    r = dict(r)
    if cripto.ativo():
        r = cripto.cifrar_cliente(r)
    con.execute(
        """INSERT INTO clientes (id, nome, email, cpf, nascimento, cidade, atualizado_em, _carregado_em, _execucao)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET nome=excluded.nome, email=excluded.email, cpf=excluded.cpf,
             nascimento=excluded.nascimento, cidade=excluded.cidade, atualizado_em=excluded.atualizado_em,
             _carregado_em=excluded._carregado_em, _execucao=excluded._execucao""",
        (r["id"], r["nome"], r["email"], r["cpf"], r["nascimento"], r["cidade"], r["atualizado_em"],
         comum.agora(), exe))


def gravar_pedido(con, r, exe):
    con.execute(
        """INSERT INTO pedidos (id, cliente_id, valor_centavos, status, criado_em, atualizado_em, observacao,
             _carregado_em, _execucao) VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET cliente_id=excluded.cliente_id, valor_centavos=excluded.valor_centavos,
             status=excluded.status, criado_em=excluded.criado_em, atualizado_em=excluded.atualizado_em,
             observacao=excluded.observacao, _carregado_em=excluded._carregado_em, _execucao=excluded._execucao""",
        (r["id"], r["cliente_id"], r["valor_centavos"], r["status"], r["criado_em"], r["atualizado_em"],
         r["observacao"], comum.agora(), exe))


def gravar_navegacao(con, r, exe):
    """Anexação idempotente: a chave do evento impede a duplicata."""
    cur = con.execute(
        "INSERT OR IGNORE INTO navegacao (evento_id, cliente_id, ip, pagina, quando, _carregado_em, _execucao)"
        " VALUES (?,?,?,?,?,?,?)",
        (r["evento_id"], r["cliente_id"], r["ip"], r["pagina"], r["quando"], comum.agora(), exe))
    return cur.rowcount


def contagens(con=None):
    fechar = con is None
    con = con or abrir()
    out = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("clientes", "pedidos", "navegacao")}
    out["receita_paga"] = con.execute(
        "SELECT COALESCE(SUM(valor_centavos),0) FROM pedidos WHERE status='pago'").fetchone()[0]
    if fechar:
        con.close()
    return out


def cliente(con, cid):
    """Cadastro com os campos pessoais já revelados (se a chave existir)."""
    r = con.execute("SELECT * FROM clientes WHERE id = ?", (cid,)).fetchone()
    if r is None:
        return None
    d = dict(r)
    for c in cripto.CAMPOS_PESSOAIS:
        d[c] = cripto.revelar(cid, d[c])
    return d
