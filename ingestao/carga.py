"""Missão 1 · carga incremental, por marca-d'água, com mesclagem pela chave.

- clientes e pedidos: lê da origem só o que tem atualizado_em maior que a marca-d'água
  (guardada na tabela marca_dagua da própria camada bronze, fora do código) e mescla por id.
- navegacao (carga em lote da Missão 1): anexa só o que ainda não chegou; evento_id impede duplicata.
Rodar de novo com a mesma entrada não muda o resultado (idempotência)."""
import comum
from ingestao import bronze

TABELAS_PADRAO = ("clientes", "pedidos", "navegacao")


def executar(tabelas=TABELAS_PADRAO):
    org = comum.conectar("origem", somente_leitura=True)
    br = bronze.abrir()
    exe = bronze.nova_execucao(br, "carga")
    lidas = {}
    for t in tabelas:
        if t in ("clientes", "pedidos"):
            wm = br.execute("SELECT valor FROM marca_dagua WHERE tabela = ?", (t,)).fetchone()
            wm = wm[0] if wm else ""
            rows = [dict(r) for r in org.execute(
                f"SELECT * FROM {t} WHERE atualizado_em > ? ORDER BY atualizado_em, id", (wm,))]
            grava = bronze.gravar_cliente if t == "clientes" else bronze.gravar_pedido
            for r in rows:
                grava(br, r, exe)
            if rows:
                novo = max(r["atualizado_em"] for r in rows)
                br.execute("INSERT INTO marca_dagua VALUES (?, ?) ON CONFLICT(tabela) DO UPDATE SET valor = excluded.valor",
                           (t, novo))
            lidas[t] = len(rows)
        elif t == "navegacao":
            ult = br.execute("SELECT COALESCE(MAX(evento_id), 0) FROM navegacao").fetchone()[0]
            rows = [dict(r) for r in org.execute("SELECT * FROM navegacao WHERE evento_id > ? ORDER BY evento_id", (ult,))]
            for r in rows:
                bronze.gravar_navegacao(br, r, exe)
            lidas[t] = len(rows)
    br.commit()
    resumo = bronze.contagens(br)
    br.close()
    org.close()
    return {"execucao": exe, "lidas": lidas, "total_lidas": sum(lidas.values()), "bronze": resumo}
