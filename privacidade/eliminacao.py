"""Lista de eliminação: a prova de que um titular foi esquecido. Guarda só a chave, a data e as moradas
tratadas, sem nenhum dado pessoal. É reaplicada depois de cada restauração (o eliminado não volta)."""
import json

import comum

ARQUIVO = comum.RAIZ / "privacidade" / "lista_eliminacao.json"


def ler():
    if not ARQUIVO.exists():
        return []
    return json.loads(ARQUIVO.read_text(encoding="utf-8"))


def chaves_eliminadas():
    return {int(r["chave"]) for r in ler()}


def registrar(chave, moradas):
    lista = ler()
    if any(int(r["chave"]) == int(chave) for r in lista):
        return False
    lista.append({"chave": int(chave), "data": comum.agora(), "moradas": moradas})
    ARQUIVO.write_text(json.dumps(lista, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True
