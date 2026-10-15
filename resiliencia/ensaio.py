"""Ensaio do desastre (Missão 9), cronometrado:
apaga a bronze -> restaura a cópia -> reaplica o log -> reaplica a lista de eliminação -> carrega o lote do dia 3
-> reconstrói a silver e a gold. O tempo medido é o RTO real."""
import time

import comum
from ingestao import bronze, cdc, fluxo
from privacidade import eliminacao, esquecer
from qualidade import validador
from resiliencia import backup, reconstruir
from seguranca import cripto


def ensaiar(nome="dia1", da_isolada=False, relogio=time.perf_counter):
    etapas = []
    t0 = relogio()

    def marca(txt, extra=""):
        etapas.append((txt, relogio() - t0, extra))

    # o desastre: a bronze some (e a silver/gold com ela)
    for b in ("bronze", "silver", "gold"):
        comum.apagar_banco(b)
    marca("desastre: bronze, silver e gold apagadas")

    r = backup.restaurar(nome, da_isolada=da_isolada)
    restaurada = bronze.contagens()
    with_5 = bronze.abrir()
    tem_cliente_5 = with_5.execute("SELECT 1 FROM clientes WHERE id = 5").fetchone() is not None
    with_5.close()
    marca("cópia restaurada e verificada (SHA-256 + integridade)", f"{restaurada} cliente 5 presente: {tem_cliente_5}")

    n_mud = cdc.sincronizar()
    n_nav, _ = fluxo.passo("bronze")
    marca("log reaplicado", f"{n_mud} eventos de mudanças, {n_nav} do tópico de navegação")

    for l in eliminacao.ler():
        esquecer.esquecer(l["chave"], registrar=False, reconstruir=False)
    marca("lista de eliminação reaplicada", f"{len(eliminacao.ler())} titular(es)")

    if cripto.ativo():
        n = cripto.proteger_bronze()
        marca("bronze cifrada de novo (crypto-shredding)", f"{n} cadastros")

    novas = validador.carregar_lote()
    marca("lote do dia 3 carregado", f"{novas} linhas")

    rec = reconstruir.reconstruir()
    marca("silver e gold reconstruídas", f"{rec['silver']}")

    total = relogio() - t0
    return {"etapas": etapas, "segundos": total, "restaurada": restaurada, "tem_cliente_5": tem_cliente_5,
            "reconstrucao": rec}
