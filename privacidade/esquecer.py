"""Missão 8 · o direito de ser esquecido. `esquecer <id>` trata TODAS as moradas do titular (ver moradas.md)
e registra a evidência na lista de eliminação. Rodar de novo não falha nem muda nada."""
import json
import re

import comum
from ingestao import bronze, fluxo, leitores
from privacidade import consumo, eliminacao
from seguranca import cripto, silver


def _faxina(con, nome):
    con.commit()
    con.execute("VACUUM")  # com secure_delete, o apagado não sobra nas páginas livres
    con.close()


def esquecer(cid, registrar=True, reconstruir=True):
    cid = int(cid)
    moradas = []

    # 1) origem: cadastro, eventos de navegação e o texto livre dos pedidos
    org = comum.conectar("origem")
    ids_eventos = [r[0] for r in org.execute("SELECT evento_id FROM navegacao WHERE cliente_id = ?", (cid,))]
    n = org.execute("DELETE FROM clientes WHERE id = ?", (cid,)).rowcount
    n += org.execute("DELETE FROM navegacao WHERE cliente_id = ?", (cid,)).rowcount
    n += org.execute("UPDATE pedidos SET observacao = NULL WHERE cliente_id = ? AND observacao IS NOT NULL", (cid,)).rowcount
    moradas.append("origem: clientes, navegacao, pedidos.observacao")

    # 2) log: eventos de mudanças (a carga útil do titular é zerada; o registro da exclusão por chave fica)
    for r in org.execute("SELECT seq, tabela, dados FROM mudancas WHERE dados IS NOT NULL").fetchall():
        d = json.loads(r["dados"])
        if r["tabela"] == "clientes" and d.get("id") == cid and len(d) > 1:
            org.execute("UPDATE mudancas SET dados = NULL, tombstone = 1 WHERE seq = ?", (r["seq"],))
        elif r["tabela"] == "pedidos" and d.get("cliente_id") == cid and d.get("observacao") is not None:
            d["observacao"] = None
            org.execute("UPDATE mudancas SET dados = ?, tombstone = 1 WHERE seq = ?", (json.dumps(d, ensure_ascii=False), r["seq"]))
    _faxina(org, "origem")
    moradas.append("log de mudanças (origem.mudancas): carga útil zerada, exclusão registrada por chave")

    # 3) log: tópico de navegação (lápide por chave + compactação)
    log = fluxo.abrir_log()
    if not log.execute("SELECT 1 FROM topico_navegacao WHERE lapide = 1 AND chave = ?", (str(cid),)).fetchone():
        log.execute("INSERT INTO topico_navegacao (chave, valor, lapide, publicado_em) VALUES (?, NULL, 1, ?)",
                    (str(cid), comum.agora()))
    log.execute("UPDATE topico_navegacao SET valor = NULL WHERE chave = ? AND lapide = 0 AND valor IS NOT NULL", (str(cid),))
    _faxina(log, "log")
    moradas.append("log de navegação (tópico navegacao): lápide por chave + compactação")

    # 4) estado dos leitores
    ld = leitores.abrir()
    for e in ids_eventos:
        ld.execute("DELETE FROM visitas_eventos WHERE evento_id = ?", (e,))
    ld.execute("DELETE FROM por_cliente_eventos WHERE cliente_id = ?", (cid,))
    _faxina(ld, "leitores")
    moradas.append("estado dos leitores do log (visitas, por_cliente)")

    # 5) camada bronze (e a chave do titular, no crypto-shredding)
    br = bronze.abrir()
    br.execute("DELETE FROM clientes WHERE id = ?", (cid,))
    br.execute("DELETE FROM navegacao WHERE cliente_id = ?", (cid,))
    br.execute("UPDATE pedidos SET observacao = NULL WHERE cliente_id = ? AND observacao IS NOT NULL", (cid,))
    br.execute("UPDATE pedidos_lote SET observacao = NULL WHERE cliente_id = ? AND observacao IS NOT NULL", (cid,))
    for r in br.execute("SELECT rowid, conteudo FROM quarentena").fetchall():
        d = json.loads(r["conteudo"])
        if d.get("cliente_id") == cid and d.get("observacao") is not None:
            d["observacao"] = None
            br.execute("UPDATE quarentena SET conteudo = ? WHERE rowid = ?", (json.dumps(d, ensure_ascii=False), r["rowid"]))
    _faxina(br, "bronze")
    cripto.apagar_chave(cid)
    moradas.append("camada bronze: cadastro, navegação, observação do pedido (chave do titular apagada)")

    # 6) camadas derivadas: reconstruídas sem o titular (a lista de eliminação anula o pseudônimo do pedido)
    if registrar:
        eliminacao.registrar(cid, moradas + [
            "camada silver e gold: reconstruídas sem o titular; pedido mantido sem vínculo (cliente_ps vazio)",
            "cópia de segurança: expira no prazo; nunca restaurada sem reaplicar esta lista",
            "saídas e evidências do pipeline: geradas sem dado pessoal"])
    if reconstruir:
        silver.construir(generalizar=True)
        consumo.construir_gold(k=consumo.K_PADRAO)
    return moradas


def buscar_resquicios(cid_termos, bancos=("origem", "leitores", "log", "bronze", "silver", "gold")):
    """Procura cada termo (texto, sem diferenciar maiúsculas) nos BYTES dos bancos: pega o que o SQL não mostra."""
    achados = {}
    for b in bancos:
        p = comum.caminho(b)
        if not p.exists():
            continue
        bruto = p.read_bytes().lower()
        for t in cid_termos:
            if t.lower().encode() in bruto:
                achados.setdefault(b, []).append(t)
    return achados
