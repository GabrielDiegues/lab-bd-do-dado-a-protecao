"""Regra como código (Missão 5): nenhum conjunto de classe pessoal sem retenção definida.
Também confere que o dono do contrato e a classe do contrato batem com o acordo, e que o dono é um time."""
import yaml

import comum

CLASSES = ["público", "interno", "confidencial", "pessoal", "pessoal sensível"]
PESSOAIS = ("pessoal", "pessoal sensível")


class RegraViolada(Exception):
    pass


def carregar_acordo(caminho=None):
    with open(caminho or comum.RAIZ / "governanca" / "acordo.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def mais_sensivel(classes):
    return max(classes, key=CLASSES.index)


def _vazio(v):
    return v is None or str(v).strip() in ("", "...")


def verificar(acordo=None):
    """Levanta RegraViolada com a lista do que está errado; devolve o acordo se estiver tudo certo."""
    acordo = acordo or carregar_acordo()
    erros = []
    for c in acordo["conjuntos"]:
        nome = c["nome"]
        if c.get("classe") not in CLASSES:
            erros.append(f"{nome}: classe inválida ({c.get('classe')!r})")
        if _vazio(c.get("dono")) or str(c["dono"]).lower().startswith(("sr.", "sra.", "dr.")):
            erros.append(f"{nome}: dono ausente (precisa ser um time)")
        if c.get("classe") in PESSOAIS:
            r = c.get("retencao") or {}
            if _vazio(r.get("prazo")) or _vazio(r.get("motivo")):
                erros.append(f"{nome}: conjunto de classe '{c['classe']}' sem retenção definida (prazo e motivo)")
        ac = c.get("acesso") or {}
        if any(_vazio(ac.get(k)) for k in ("pede", "aprova", "audita")):
            erros.append(f"{nome}: acesso incompleto (quem pede, quem aprova, o que se audita)")
        # contrato e acordo falam a mesma coisa
        with open(comum.RAIZ / "contratos" / f"{nome}.yaml", encoding="utf-8") as f:
            ct = yaml.safe_load(f)
        if ct.get("dono") != c.get("dono"):
            erros.append(f"{nome}: dono do contrato difere do acordo")
        esperado = mais_sensivel([k["classe"] for k in ct["campos"]])
        if c.get("classe") != esperado:
            erros.append(f"{nome}: a classe do conjunto deve ser a do campo mais sensível ({esperado})")
    if erros:
        raise RegraViolada("\n".join(erros))
    return acordo
