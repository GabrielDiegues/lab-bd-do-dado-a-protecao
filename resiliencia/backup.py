"""Missão 9 · cópia de segurança da camada bronze (a fonte de reconstrução da silver e da gold).

Cada cópia guarda: a bronze (API de backup do SQLite, consistente), os offsets dos leitores da bronze,
o cofre das chaves por titular (se existir) e um manifesto com SHA-256 para provar a integridade.
Esquema 3-2-1-1-0 do laboratório (detalhes em resiliencia/plano.md):
  cópia 1  estado/ (a própria bronze viva)             -> mesmo local
  cópia 2  <backup>/<nome>/                            -> outra pasta, fora do repositório
  cópia 3  <cofre>/copia_isolada/<nome>/ somente leitura -> "fora do site" + imutável (no laboratório, chmod 0444;
           em produção: outro provedor/conta, credencial independente e trava de retenção)"""
import hashlib
import json
import os
import shutil
import sqlite3

import comum
from ingestao import leitores

OFFSETS_DA_BRONZE = [("bronze_mudancas", "mudancas"), ("bronze", "navegacao")]


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _copiar_sqlite(origem, destino):
    src = sqlite3.connect(origem)
    dst = sqlite3.connect(destino)
    with dst:
        src.backup(dst)
    dst.close()
    src.close()


def criar(nome="dia1"):
    pos = leitores.todos()
    offsets = {f"{l}/{t}": pos.get((l, t), 0) for l, t in OFFSETS_DA_BRONZE}
    pasta = comum.pasta_backup() / nome
    if pasta.exists():
        shutil.rmtree(pasta)
    pasta.mkdir(parents=True)
    _copiar_sqlite(comum.caminho("bronze"), pasta / "bronze.db")
    if comum.caminho("chaves_titular").exists():
        _copiar_sqlite(comum.caminho("chaves_titular"), pasta / "chaves_titular.db")
    (pasta / "offsets.json").write_text(json.dumps(offsets, indent=2))
    manifesto = {a.name: sha256(a) for a in sorted(pasta.iterdir())}
    (pasta / "manifesto.json").write_text(json.dumps({"criado_em": comum.agora(), "sha256": manifesto}, indent=2))

    # cópia da chave de pseudônimo: FORA do repositório, em outro local
    cofre = comum.pasta_cofre()
    chave = os.environ.get("CHAVE_PSEUDONIMO")
    if chave:
        alvo = cofre / "chave_pseudonimo.txt"
        alvo.write_text(chave)
        os.chmod(alvo, 0o600)

    # cópia isolada e imutável (somente leitura)
    iso = cofre / "copia_isolada" / nome
    if iso.exists():
        os.chmod(iso, 0o755)
        for f in iso.iterdir():
            os.chmod(f, 0o644)
        shutil.rmtree(iso)
    shutil.copytree(pasta, iso)
    for f in iso.iterdir():
        os.chmod(f, 0o444)
    os.chmod(iso, 0o555)
    return {"pasta": str(pasta), "isolada": str(iso), "offsets": offsets, "sha256": manifesto}


def verificar(pasta):
    """0 erros no teste de restauração: manifesto confere e o banco abre íntegro."""
    erros = []
    man = json.loads((pasta / "manifesto.json").read_text())["sha256"]
    for nome, h in man.items():
        if sha256(pasta / nome) != h:
            erros.append(f"{nome}: SHA-256 não confere")
    con = sqlite3.connect(f"file:{pasta / 'bronze.db'}?mode=ro", uri=True)
    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        erros.append("bronze.db: integridade falhou")
    con.close()
    return erros


def restaurar(nome="dia1", da_isolada=False):
    pasta = (comum.pasta_cofre() / "copia_isolada" / nome) if da_isolada else (comum.pasta_backup() / nome)
    erros = verificar(pasta)
    if erros:
        raise RuntimeError("cópia inválida: " + "; ".join(erros))
    comum.apagar_banco("bronze")
    shutil.copyfile(pasta / "bronze.db", comum.caminho("bronze"))
    if (pasta / "chaves_titular.db").exists():
        comum.apagar_banco("chaves_titular")
        shutil.copyfile(pasta / "chaves_titular.db", comum.caminho("chaves_titular"))
    offsets = json.loads((pasta / "offsets.json").read_text())
    for chave, p in offsets.items():
        l, t = chave.split("/")
        leitores.salvar(l, t, p)
    return {"origem": str(pasta), "offsets": offsets}
