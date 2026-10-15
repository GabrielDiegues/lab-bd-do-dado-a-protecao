"""`reconstruir`: apaga a camada silver e a visão de consumo e as recria do zero a partir da camada bronze.
A silver é derivada: o que se protege de verdade é a bronze, o log e a chave."""
import time

from privacidade import consumo
from seguranca import silver


def reconstruir(chave=None, k=consumo.K_PADRAO):
    t0 = time.perf_counter()
    s = silver.construir(generalizar=True, chave=chave)
    g = consumo.construir_gold(k=k)
    return {"silver": s, "gold": g, "segundos": time.perf_counter() - t0}
