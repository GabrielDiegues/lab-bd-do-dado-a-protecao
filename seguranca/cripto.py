"""Crypto-shredding (extra da Missão 8): cada titular tem uma chave própria (AES-GCM)
e os campos pessoais do cadastro, na camada bronze, ficam cifrados com ela.
Apagar a chave do titular torna ilegível toda cópia daquele cadastro."""
import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import comum

PREFIXO = "enc:v1:"
CAMPOS_PESSOAIS = ("nome", "email", "cpf", "nascimento", "cidade")


def _marca():
    return comum.estado() / "cripto.ativo"


def ativo():
    return _marca().exists()


def ativar():
    _marca().write_text("1")


def _con():
    con = comum.conectar("chaves_titular")
    con.execute("CREATE TABLE IF NOT EXISTS chaves (cliente_id INTEGER PRIMARY KEY, chave BLOB NOT NULL)")
    return con


def chave_do_titular(cid, criar=False):
    con = _con()
    try:
        r = con.execute("SELECT chave FROM chaves WHERE cliente_id = ?", (int(cid),)).fetchone()
        if r is None and criar:
            k = AESGCM.generate_key(bit_length=256)
            con.execute("INSERT INTO chaves VALUES (?, ?)", (int(cid), k))
            con.commit()
            return k
        return r[0] if r else None
    finally:
        con.close()


def apagar_chave(cid):
    """O ato de esquecer: sem a chave, o que foi cifrado com ela vira ruído."""
    con = _con()
    n = con.execute("DELETE FROM chaves WHERE cliente_id = ?", (int(cid),)).rowcount
    con.commit()
    con.execute("VACUUM")
    con.close()
    return n


def cifrar(cid, texto):
    if texto is None or str(texto).startswith(PREFIXO):
        return texto
    k = chave_do_titular(cid, criar=True)
    nonce = os.urandom(12)
    ct = AESGCM(k).encrypt(nonce, str(texto).encode("utf-8"), str(cid).encode())
    return PREFIXO + base64.b64encode(nonce + ct).decode()


def revelar(cid, valor):
    """Devolve o texto claro; None se o valor está cifrado e a chave foi apagada."""
    if valor is None or not str(valor).startswith(PREFIXO):
        return valor
    k = chave_do_titular(cid)
    if k is None:
        return None
    raw = base64.b64decode(str(valor)[len(PREFIXO):])
    try:
        return AESGCM(k).decrypt(raw[:12], raw[12:], str(cid).encode()).decode("utf-8")
    except InvalidTag:
        return None


def cifrar_cliente(row):
    """row: dict com id + campos do cadastro. Devolve cópia com os campos pessoais cifrados."""
    out = dict(row)
    for c in CAMPOS_PESSOAIS:
        out[c] = cifrar(row["id"], row.get(c))
    return out


def proteger_bronze():
    """Cifra, no lugar, o cadastro que já está na camada bronze. Idempotente."""
    con = comum.conectar("bronze")
    n = 0
    for r in con.execute("SELECT * FROM clientes").fetchall():
        d = dict(r)
        novo = cifrar_cliente(d)
        if novo != d:
            con.execute("UPDATE clientes SET nome=?, email=?, cpf=?, nascimento=?, cidade=? WHERE id=?",
                        (novo["nome"], novo["email"], novo["cpf"], novo["nascimento"], novo["cidade"], d["id"]))
            n += 1
    con.commit()
    con.execute("VACUUM")  # o claro não pode sobrar em páginas livres
    con.close()
    ativar()
    return n
