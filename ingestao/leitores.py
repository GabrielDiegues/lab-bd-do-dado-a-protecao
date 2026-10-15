"""Estado dos leitores do log: um offset por (leitor, tópico) e o que cada leitor acumulou.
O log não sabe quem leu o quê; quem guarda a posição é o leitor."""
import comum

ESQUEMA = """
CREATE TABLE IF NOT EXISTS offsets (leitor TEXT, topico TEXT, pos INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (leitor, topico));
CREATE TABLE IF NOT EXISTS visitas_eventos (evento_id INTEGER PRIMARY KEY, pagina TEXT);
CREATE TABLE IF NOT EXISTS por_cliente_eventos (evento_id INTEGER PRIMARY KEY, cliente_id INTEGER);
CREATE TABLE IF NOT EXISTS produtor (topico TEXT PRIMARY KEY, ultimo_evento INTEGER NOT NULL DEFAULT 0);
"""


def abrir():
    con = comum.conectar("leitores")
    con.executescript(ESQUEMA)
    return con


def pos(leitor, topico):
    con = abrir()
    r = con.execute("SELECT pos FROM offsets WHERE leitor=? AND topico=?", (leitor, topico)).fetchone()
    con.close()
    return r[0] if r else 0


def salvar(leitor, topico, p):
    con = abrir()
    con.execute("INSERT INTO offsets VALUES (?,?,?) ON CONFLICT(leitor, topico) DO UPDATE SET pos = excluded.pos",
                (leitor, topico, p))
    con.commit()
    con.close()


def todos():
    con = abrir()
    out = {(r["leitor"], r["topico"]): r["pos"] for r in con.execute("SELECT * FROM offsets")}
    con.close()
    return out
