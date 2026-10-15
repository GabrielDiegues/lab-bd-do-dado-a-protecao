"""A origem: o banco da loja. Sem chave estrangeira entre as tabelas:
o pedido precisa sobreviver à exclusão do cliente."""
import comum

ESQUEMA = """
CREATE TABLE clientes (
  id INTEGER PRIMARY KEY, nome TEXT, email TEXT, cpf TEXT,
  nascimento TEXT, cidade TEXT, atualizado_em TEXT);
CREATE TABLE pedidos (
  id INTEGER PRIMARY KEY, cliente_id INTEGER, valor_centavos INTEGER, status TEXT,
  criado_em TEXT, atualizado_em TEXT, observacao TEXT);
CREATE TABLE navegacao (
  evento_id INTEGER PRIMARY KEY, cliente_id INTEGER, ip TEXT, pagina TEXT, quando TEXT);
-- log de mudanças (Trilha A): só se anexa; preenchido por gatilhos
CREATE TABLE mudancas (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, tabela TEXT NOT NULL, op TEXT NOT NULL,
  chave TEXT NOT NULL, dados TEXT, quando TEXT, tombstone INTEGER NOT NULL DEFAULT 0);
"""

COLS = {
    "clientes": ["id", "nome", "email", "cpf", "nascimento", "cidade", "atualizado_em"],
    "pedidos": ["id", "cliente_id", "valor_centavos", "status", "criado_em", "atualizado_em", "observacao"],
}


def iniciar(dia1=None):
    """Recria a origem no estado do dia 1."""
    dia1 = dia1 or comum.RAIZ / "dados" / "dia1"
    comum.apagar_banco("origem")
    con = comum.conectar("origem")
    con.executescript(ESQUEMA)
    for r in comum.ler_csv(dia1 / "clientes.csv"):
        con.execute("INSERT INTO clientes VALUES (?,?,?,?,?,?,?)",
                    (int(r["id"]), r["nome"], r["email"], r["cpf"], r["nascimento"], r["cidade"], r["atualizado_em"]))
    for r in comum.ler_csv(dia1 / "pedidos.csv"):
        con.execute("INSERT INTO pedidos VALUES (?,?,?,?,?,?,?)",
                    (int(r["id"]), comum.como_int(r["cliente_id"]), int(r["valor_centavos"]), r["status"],
                     r["criado_em"], r["atualizado_em"], r["observacao"]))
    for r in comum.ler_csv(dia1 / "navegacao.csv"):
        con.execute("INSERT INTO navegacao VALUES (?,?,?,?,?)",
                    (int(r["evento_id"]), comum.como_int(r["cliente_id"]), r["ip"], r["pagina"], r["quando"]))
    con.commit()
    con.close()


def contagens():
    con = comum.conectar("origem", somente_leitura=True)
    out = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("clientes", "pedidos", "navegacao")}
    out["receita_paga"] = con.execute(
        "SELECT COALESCE(SUM(valor_centavos),0) FROM pedidos WHERE status='pago'").fetchone()[0]
    con.close()
    return out


def aplicar_dia2():
    """Aplica as mudanças do dia 2 (uma vez só: se o cliente 7 já existe, não repete)."""
    con = comum.conectar("origem")
    if con.execute("SELECT 1 FROM clientes WHERE id = 7").fetchone():
        con.close()
        return False
    con.executescript((comum.RAIZ / "dados" / "dia2" / "mudancas.sql").read_text(encoding="utf-8"))
    con.commit()
    con.close()
    return True
