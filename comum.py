"""Caminhos, conexões e utilidades compartilhadas por todo o pipeline."""
import csv
import datetime
import os
import pathlib
import sqlite3

RAIZ = pathlib.Path(__file__).resolve().parent


def estado():
    """Pasta dos bancos (um arquivo SQLite por camada). LAB_ESTADO troca a pasta."""
    d = pathlib.Path(os.environ.get("LAB_ESTADO", RAIZ / "estado"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def pasta_backup():
    """Cópias de segurança ficam FORA do repositório."""
    d = pathlib.Path(os.environ.get("LAB_BACKUP", RAIZ.parent / "backup-lab-bd"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def pasta_cofre():
    """Cópia isolada (outro local) e cópia da chave: também fora do repositório."""
    d = pathlib.Path(os.environ.get("LAB_COFRE", RAIZ.parent / "cofre-lab-bd"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def pasta_evidencias():
    d = pathlib.Path(os.environ.get("LAB_EVIDENCIAS", RAIZ / "evidencias"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def agora():
    """Momento da carga. LAB_AGORA (ISO) permite reproduzir uma execução."""
    return os.environ.get("LAB_AGORA") or datetime.datetime.now().isoformat(timespec="seconds")


BANCOS = ("origem", "leitores", "log", "bronze", "silver", "gold", "chaves_titular")


def caminho(nome):
    return estado() / f"{nome}.db"


def conectar(nome, somente_leitura=False):
    p = caminho(nome)
    if somente_leitura:
        con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=30)
    else:
        con = sqlite3.connect(p, timeout=30)
        con.execute("PRAGMA secure_delete = ON")  # o que se apaga não fica em páginas livres
    con.row_factory = sqlite3.Row
    return con


def apagar_banco(nome):
    p = caminho(nome)
    for sufixo in ("", "-journal", "-wal", "-shm"):
        q = pathlib.Path(str(p) + sufixo)
        if q.exists():
            q.unlink()


def zerar_estado():
    for nome in BANCOS:
        apagar_banco(nome)
    marca = estado() / "cripto.ativo"
    if marca.exists():
        marca.unlink()


def ler_csv(arquivo):
    """Lê CSV; campo vazio vira NULL."""
    with open(arquivo, newline="", encoding="utf-8") as f:
        return [{k: (v if v != "" else None) for k, v in linha.items()} for linha in csv.DictReader(f)]


def como_int(v):
    return int(v) if v is not None else None


def reais(centavos):
    s = f"{abs(centavos) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if centavos < 0 else "") + "R$ " + s
