"""Varredor (Missão 5): procura e-mail, telefone, CPF e IP nas colunas da camada bronze, inclusive nas de
texto livre, e confronta com a classe declarada nos contratos. O que é pessoal e não foi declarado é o
dado pessoal escondido."""
import re

import yaml

import comum
from governanca import regras
from ingestao import bronze
from seguranca import cripto

PADROES = {
    "e-mail": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "telefone": re.compile(r"\(\d{2}\)\s?9?\d{4}-?\d{4}"),
    "CPF": re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    "IP": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}
CHAVES = {"clientes": "id", "pedidos": "id", "navegacao": "evento_id"}


def classes_declaradas():
    out = {}
    for conj in CHAVES:
        with open(comum.RAIZ / "contratos" / f"{conj}.yaml", encoding="utf-8") as f:
            ct = yaml.safe_load(f)
        for c in ct["campos"]:
            out[(conj, c["nome"])] = c.get("classe", "interno")
    return out


def varrer(classes=None):
    """classes: {(conjunto, coluna): classe}; por padrão, a dos contratos.
    Devolve lista de achados {tabela, coluna, tipos, ids, declarada, escondido}."""
    classes = classes or classes_declaradas()
    br = bronze.abrir()
    achados = {}
    for tabela, pk in CHAVES.items():
        colunas = [c[1] for c in br.execute(f"PRAGMA table_info({tabela})") if not c[1].startswith("_")]
        for r in br.execute(f"SELECT * FROM {tabela}"):
            for col in colunas:
                v = r[col]
                if tabela == "clientes":
                    v = cripto.revelar(r["id"], v)
                if not isinstance(v, str):
                    continue
                for tipo, rx in PADROES.items():
                    if rx.search(v):
                        a = achados.setdefault((tabela, col), {"tipos": set(), "ids": []})
                        a["tipos"].add(tipo)
                        a["ids"].append(r[pk])
    br.close()
    out = []
    for (tabela, col), a in sorted(achados.items()):
        decl = classes.get((tabela, col), "interno")
        out.append({"tabela": tabela, "coluna": col, "tipos": sorted(a["tipos"]), "ids": sorted(set(a["ids"])),
                    "declarada": decl, "escondido": decl not in regras.PESSOAIS})
    return out
