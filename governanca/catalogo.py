"""Gera governanca/catalogo.md a partir dos contratos e do acordo: nada é digitado duas vezes."""
import yaml

import comum
from governanca import regras


def gerar(saida=None):
    acordo = regras.carregar_acordo()
    linhas = ["# Catálogo de dados", "",
              "_Gerado por `governanca/catalogo.py` a partir de `contratos/*.yaml` e `governanca/acordo.yaml`. Não edite à mão._", ""]
    for c in acordo["conjuntos"]:
        with open(comum.RAIZ / "contratos" / f"{c['nome']}.yaml", encoding="utf-8") as f:
            ct = yaml.safe_load(f)
        r, ac = c["retencao"], c["acesso"]
        linhas += [f"## {c['nome']}", "", ct.get("descricao", ""), "",
                   f"- **Dono:** {c['dono']}",
                   f"- **Classe:** {c['classe']}",
                   f"- **Frescor:** {ct.get('frescor', '—')}",
                   f"- **Retenção:** {r['prazo']}. {r['motivo']}",
                   f"- **Acesso:** pede {ac['pede']}; aprova {ac['aprova']}; audita {ac['audita']}", "",
                   "| Campo | Tipo | Obrigatório | Classe | Descrição | Finalidade |", "|---|---|---|---|---|---|"]
        for k in ct["campos"]:
            linhas.append("| `{}` | {} | {} | {} | {} | {} |".format(
                k["nome"], k.get("tipo", ""), "sim" if k.get("obrigatorio") else "não", k.get("classe", "—"),
                k.get("descricao", ""), k.get("finalidade", "—")))
        linhas.append("")
    texto = "\n".join(linhas)
    destino = saida or comum.RAIZ / "governanca" / "catalogo.md"
    destino.write_text(texto, encoding="utf-8")
    return texto
