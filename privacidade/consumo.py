"""Missão 7 · a visão de consumo: o analista recebe agregado, não a tabela.
K-anonimato: cada combinação de quase-identificadores aparece em pelo menos K pessoas.
Limiar mínimo K: cidade com menos de K clientes aparece como suprimida."""
import comum

K_PADRAO = 2


def medir_k(coluna_idade="faixa_etaria"):
    """K da tabela de clientes da silver, usando cidade + (faixa etária | nascimento).
    Devolve {tamanho_do_menor_grupo, combinacoes, unicas, grupos}."""
    sv = comum.conectar("silver", somente_leitura=True)
    grupos = {}
    for r in sv.execute(f"SELECT cidade, {coluna_idade} AS q FROM clientes"):
        grupos[(r["cidade"], r["q"])] = grupos.get((r["cidade"], r["q"]), 0) + 1
    sv.close()
    return {"k": min(grupos.values()) if grupos else 0, "combinacoes": len(grupos),
            "unicas": sum(1 for n in grupos.values() if n == 1), "grupos": grupos}


def construir_gold(k=K_PADRAO):
    """gold.receita_por_cidade: cidade, número de clientes e receita paga; suprime cidade com menos de K clientes."""
    sv = comum.conectar("silver", somente_leitura=True)
    linhas = sv.execute(
        """SELECT c.cidade AS cidade, COUNT(DISTINCT c.cliente_ps) AS clientes,
                  COALESCE(SUM(CASE WHEN p.status = 'pago' THEN p.valor_centavos END), 0) AS receita
           FROM clientes c LEFT JOIN pedidos p ON p.cliente_ps = c.cliente_ps
           GROUP BY c.cidade ORDER BY c.cidade""").fetchall()
    total = sv.execute("SELECT COALESCE(SUM(valor_centavos),0) FROM pedidos WHERE status='pago'").fetchone()[0]
    sv.close()
    comum.apagar_banco("gold")
    g = comum.conectar("gold")
    g.execute("CREATE TABLE receita_por_cidade (cidade TEXT, clientes INTEGER, receita_centavos INTEGER, suprimida INTEGER)")
    g.execute("CREATE TABLE parametros (nome TEXT PRIMARY KEY, valor TEXT)")
    g.execute("INSERT INTO parametros VALUES ('K', ?)", (str(k),))
    g.execute("INSERT INTO parametros VALUES ('receita_total_centavos', ?)", (str(total),))
    for r in linhas:
        sup = r["clientes"] < k
        g.execute("INSERT INTO receita_por_cidade VALUES (?,?,?,?)",
                  (r["cidade"], r["clientes"], None if sup else r["receita"], 1 if sup else 0))
    g.commit()
    g.close()
    return ler_gold()


def ler_gold():
    g = comum.conectar("gold", somente_leitura=True)
    linhas = [dict(r) for r in g.execute("SELECT * FROM receita_por_cidade ORDER BY cidade")]
    total = int(g.execute("SELECT valor FROM parametros WHERE nome='receita_total_centavos'").fetchone()[0])
    g.close()
    return {"linhas": linhas, "total": total}
