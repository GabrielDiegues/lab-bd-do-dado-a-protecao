"""Missão 2 · captura de mudanças (Trilha A, sem infraestrutura).

Escolha: uma tabela `mudancas` na própria origem, preenchida por GATILHOS do banco. Assim toda
inserção, alteração ou exclusão entra no log na ordem do commit, seja qual for o programa que a fez
(a consulta por atualizado_em não enxerga o DELETE). O pipeline guarda o offset (seq do último evento
aplicado) e, a cada execução, aplica só o que veio depois, em ordem."""
import json

import comum
from ingestao import bronze, leitores

LEITOR = "bronze_mudancas"
TOPICO = "mudancas"


def _json_cols(prefixo, cols):
    return ", ".join(f"'{c}', {prefixo}.{c}" for c in cols)


def ligar_captura():
    from ingestao.origem import COLS
    con = comum.conectar("origem")
    for t, cols in COLS.items():
        for gatilho in (f"cdc_{t}_ins", f"cdc_{t}_upd", f"cdc_{t}_del"):
            con.execute(f"DROP TRIGGER IF EXISTS {gatilho}")
        novo = _json_cols("NEW", cols)
        con.execute(f"""CREATE TRIGGER cdc_{t}_ins AFTER INSERT ON {t} BEGIN
            INSERT INTO mudancas (tabela, op, chave, dados, quando)
            VALUES ('{t}', 'inserção', NEW.id, json_object({novo}), strftime('%Y-%m-%dT%H:%M:%S','now')); END""")
        con.execute(f"""CREATE TRIGGER cdc_{t}_upd AFTER UPDATE ON {t} BEGIN
            INSERT INTO mudancas (tabela, op, chave, dados, quando)
            VALUES ('{t}', 'alteração', NEW.id, json_object({novo}), strftime('%Y-%m-%dT%H:%M:%S','now')); END""")
        # a exclusão leva só a chave: o log não precisa carregar a pessoa para apagá-la
        con.execute(f"""CREATE TRIGGER cdc_{t}_del AFTER DELETE ON {t} BEGIN
            INSERT INTO mudancas (tabela, op, chave, dados, quando)
            VALUES ('{t}', 'exclusão', OLD.id, json_object('id', OLD.id), strftime('%Y-%m-%dT%H:%M:%S','now')); END""")
    con.commit()
    con.close()


def eventos(desde=0):
    con = comum.conectar("origem", somente_leitura=True)
    rows = [dict(r) for r in con.execute("SELECT * FROM mudancas WHERE seq > ? ORDER BY seq", (desde,))]
    con.close()
    return rows


def _aplicar(br, ev, exe):
    tabela, op = ev["tabela"], ev["op"]
    if op == "exclusão":
        br.execute(f"DELETE FROM {tabela} WHERE id = ?", (int(ev["chave"]),))
        return
    if ev["dados"] is None:  # carga útil já eliminada (lápide): nada a aplicar
        return
    dados = json.loads(ev["dados"])
    if tabela == "clientes":
        bronze.gravar_cliente(br, dados, exe)
    elif tabela == "pedidos":
        bronze.gravar_pedido(br, dados, exe)


def sincronizar(desde=None):
    """Aplica na bronze os eventos depois do offset salvo (ou depois de `desde`, para reaplicar).
    Salva o offset DEPOIS de aplicar: se cair no meio, repete, e repetir não muda o resultado."""
    pos = leitores.pos(LEITOR, TOPICO) if desde is None else desde
    evs = eventos(pos)
    br = bronze.abrir()
    exe = bronze.nova_execucao(br, "cdc")
    for ev in evs:
        _aplicar(br, ev, exe)
    br.commit()
    br.close()
    if evs:
        leitores.salvar(LEITOR, TOPICO, max(pos, evs[-1]["seq"]))
    return len(evs)
