"""Pseudônimo estável: cliente_ps = HMAC-SHA-256(CHAVE_PSEUDONIMO, id do cliente).
A chave vem da variável de ambiente e nunca entra no código nem no repositório."""
import hashlib
import hmac
import os


def chave():
    v = os.environ.get("CHAVE_PSEUDONIMO")
    if not v:
        raise SystemExit("Defina CHAVE_PSEUDONIMO (ex.: export CHAVE_PSEUDONIMO=$(python3 -c "
                         "'import secrets; print(secrets.token_hex(32))')). Sem ela não há pseudônimo.")
    return v


def pseudonimo(cliente_id, k=None):
    if cliente_id is None:
        return None
    return hmac.new((k or chave()).encode(), str(int(cliente_id)).encode(), hashlib.sha256).hexdigest()
