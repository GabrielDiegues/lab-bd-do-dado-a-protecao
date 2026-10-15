"""Missão 3 · o tópico `navegacao`: um log, vários leitores (Trilha A: tabela em que só se anexa).

- O produtor publica os eventos da origem e não sabe quem vai ler.
- Cada leitor guarda o PRÓPRIO offset (em leitores.db). O log guarda por tempo, não até ser lido.
- Decisão sobre o offset: salvar DEPOIS de processar (entrega pelo menos uma vez) e processar de forma
  idempotente (INSERT OR IGNORE pela chave do evento). Se o leitor cair entre processar e salvar, ao voltar
  ele repete aquele evento, e repetir não conta duas vezes. Salvar antes inverteria o risco: perderia um.
- Lápide (lapide=1): evento sem carga com a chave de um titular eliminado. Quem lê aplica a exclusão;
  a compactação (privacidade/esquecer.py) zera a carga dos eventos antigos dessa chave."""
import json
import threading
import time

import comum
from ingestao import bronze, leitores

TOPICO = "navegacao"
ESQUEMA_LOG = """
CREATE TABLE IF NOT EXISTS topico_navegacao (
  off INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT NOT NULL, valor TEXT, lapide INTEGER NOT NULL DEFAULT 0,
  publicado_em TEXT);
"""


def abrir_log(somente_leitura=False):
    con = comum.conectar("log", somente_leitura=somente_leitura)
    if not somente_leitura:
        con.executescript(ESQUEMA_LOG)
    return con


# ---------------------------------------------------------------- produtor
def eventos_a_publicar():
    org = comum.conectar("origem", somente_leitura=True)
    ld = leitores.abrir()
    ult = ld.execute("SELECT ultimo_evento FROM produtor WHERE topico = ?", (TOPICO,)).fetchone()
    ult = ult[0] if ult else 0
    rows = [dict(r) for r in org.execute("SELECT * FROM navegacao WHERE evento_id > ? ORDER BY evento_id", (ult,))]
    org.close()
    ld.close()
    return rows


def publicar(ev):
    """Anexa um evento ao tópico. A chave é o cliente_id, para manter a ordem por cliente."""
    log = abrir_log()
    chave = "" if ev["cliente_id"] is None else str(ev["cliente_id"])
    log.execute("INSERT INTO topico_navegacao (chave, valor, publicado_em) VALUES (?,?,?)",
                (chave, json.dumps(ev, ensure_ascii=False), comum.agora()))
    log.commit()
    log.close()
    ld = leitores.abrir()
    ld.execute("INSERT INTO produtor VALUES (?,?) ON CONFLICT(topico) DO UPDATE SET ultimo_evento = excluded.ultimo_evento",
               (TOPICO, ev["evento_id"]))
    ld.commit()
    ld.close()


def cabeca():
    log = abrir_log()
    h = log.execute("SELECT COALESCE(MAX(off), 0) FROM topico_navegacao").fetchone()[0]
    log.close()
    return h


# ---------------------------------------------------------------- leitores
def _ler(pos, limite=None):
    log = abrir_log()
    sql = "SELECT * FROM topico_navegacao WHERE off > ? ORDER BY off" + (f" LIMIT {int(limite)}" if limite else "")
    rows = [dict(r) for r in log.execute(sql, (pos,))]
    log.close()
    return rows


def _aplica_visitas(m):
    if m["lapide"] or m["valor"] is None:
        return  # visitas são agregadas por página: nada por cliente a apagar aqui
    ev = json.loads(m["valor"])
    ld = leitores.abrir()
    ld.execute("INSERT OR IGNORE INTO visitas_eventos VALUES (?,?)", (ev["evento_id"], ev["pagina"]))
    ld.commit()
    ld.close()


def _aplica_por_cliente(m):
    ld = leitores.abrir()
    if m["lapide"]:
        ld.execute("DELETE FROM por_cliente_eventos WHERE cliente_id = ?", (int(m["chave"]),))
    elif m["valor"] is not None:
        ev = json.loads(m["valor"])
        ld.execute("INSERT OR IGNORE INTO por_cliente_eventos VALUES (?,?)", (ev["evento_id"], ev["cliente_id"]))
    ld.commit()
    ld.close()


def _aplica_bronze(m, exe, br):
    if m["lapide"]:
        br.execute("DELETE FROM navegacao WHERE cliente_id = ?", (int(m["chave"]),))
    elif m["valor"] is not None:
        bronze.gravar_navegacao(br, json.loads(m["valor"]), exe)


APLICADORES = {"visitas": _aplica_visitas, "por_cliente": _aplica_por_cliente}


def passo(leitor, derrubar_apos=None, salvar_ultimo=True):
    """Um passo do leitor: lê o que veio depois do offset DELE, processa, salva o offset.
    derrubar_apos=n simula uma queda depois de n eventos processados; salvar_ultimo=False simula a queda
    entre processar e salvar. Devolve (processados, caiu)."""
    pos = leitores.pos(leitor, TOPICO)
    msgs = _ler(pos)
    br = bronze.abrir() if leitor == "bronze" else None
    exe = bronze.nova_execucao(br, "fluxo") if br else None
    n = 0
    caiu = False
    for m in msgs:
        if leitor == "bronze":
            _aplica_bronze(m, exe, br)
            br.commit()
        else:
            APLICADORES[leitor](m)
        n += 1
        if derrubar_apos is not None and n >= derrubar_apos:
            caiu = True
            if salvar_ultimo:
                leitores.salvar(leitor, TOPICO, m["off"])
            break
        leitores.salvar(leitor, TOPICO, m["off"])
    if br:
        br.close()
    return n, caiu


# ---------------------------------------------------------------- consultas de apoio
def visitas_por_pagina():
    ld = leitores.abrir()
    out = {r[0]: r[1] for r in ld.execute("SELECT pagina, COUNT(*) FROM visitas_eventos GROUP BY pagina ORDER BY 1")}
    ld.close()
    return out


def eventos_por_cliente():
    ld = leitores.abrir()
    out = {r[0]: r[1] for r in ld.execute("SELECT cliente_id, COUNT(*) FROM por_cliente_eventos GROUP BY cliente_id")}
    ld.close()
    return out


def eventos_no_log():
    log = abrir_log()
    n = log.execute("SELECT COUNT(*) FROM topico_navegacao WHERE lapide = 0").fetchone()[0]
    log.close()
    return n


# ---------------------------------------------------------------- demonstrações
def demo_simulada(intervalo_bronze=5, derrubar_visitas_apos=None, verboso=None):
    """Roda o cenário da missão em tempo SIMULADO (1 tick = 1 segundo de evento): o produtor publica um
    evento por tick, o leitor rápido lê a cada tick, a bronze acorda a cada `intervalo_bronze` ticks.
    Se derrubar_visitas_apos=n, o leitor `visitas` cai depois de n eventos e volta quando o produtor termina.
    Devolve a linha do tempo [(t, cabeca, lag_visitas, lag_bronze)]."""
    linhas = []
    vivo_visitas = True
    pend = eventos_a_publicar()
    for t, ev in enumerate(pend, start=1):
        publicar(ev)
        if vivo_visitas:
            n, caiu = passo("visitas", derrubar_apos=None)
            if derrubar_visitas_apos is not None and leitores.pos("visitas", TOPICO) >= derrubar_visitas_apos:
                vivo_visitas = False
        h = cabeca()
        # atraso medido antes de a bronze acordar: é o pior momento dela
        linhas.append((t, h, h - leitores.pos("visitas", TOPICO), h - leitores.pos("bronze", TOPICO)))
        if verboso:
            verboso(linhas[-1])
        if t % intervalo_bronze == 0:
            passo("bronze")
    passo("bronze")  # produtor terminou: a bronze acorda uma última vez
    passo("visitas")  # e o leitor derrubado volta, retomando do offset salvo
    return linhas


def demo_tempo_real(escala=1.0):
    """Produtor (1 evento/s), leitor rápido e bronze (a cada 5 s) em threads de verdade.
    `escala` encurta os tempos (ex.: 0.05) para testar."""
    fim = threading.Event()

    def produtor():
        for ev in eventos_a_publicar():
            publicar(ev)
            time.sleep(1.0 * escala)
        fim.set()

    def rapido():
        while not fim.is_set():
            passo("visitas")
            time.sleep(0.05 * escala)
        passo("visitas")

    def lento():
        while not fim.is_set():
            time.sleep(5.0 * escala)
            passo("bronze")
        passo("bronze")

    ts = [threading.Thread(target=f) for f in (produtor, rapido, lento)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
