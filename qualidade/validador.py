"""Missão 4 · o validador. As regras vêm do arquivo de contrato (contratos/*.yaml), não do código.

Regras entendidas: tipo (inteiro | texto | data | data_hora), obrigatorio, unico, minimo, dominio,
maximo (número, ou "momento da carga" para data_hora). Linha reprovada vai para a quarentena com o
motivo e a execução em que chegou; o restante do lote segue."""
import datetime
import json

import yaml

import comum
from ingestao import bronze


def carregar_contrato(conjunto):
    with open(comum.RAIZ / "contratos" / f"{conjunto}.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _tipo_ok(tipo, v):
    try:
        if tipo == "inteiro":
            if isinstance(v, bool):
                return False
            int(v)
        elif tipo == "data_hora":
            datetime.datetime.fromisoformat(str(v))
        elif tipo == "data":
            datetime.date.fromisoformat(str(v))
    except (TypeError, ValueError):
        return False
    return True


def motivo(linha, contrato, vistos, momento):
    """Primeiro motivo de reprovação da linha, ou None se passa. `vistos` guarda as chaves únicas já aceitas."""
    for c in contrato["campos"]:
        nome, v = c["nome"], linha.get(c["nome"])
        if v is None:
            if c.get("obrigatorio"):
                return f"{nome} ausente"
            continue
        if not _tipo_ok(c.get("tipo"), v):
            return f"{nome} com tipo inválido"
        if "minimo" in c and int(v) < c["minimo"]:
            return f"{nome} negativo" if c["minimo"] == 0 else f"{nome} abaixo do mínimo"
        if "dominio" in c and v not in c["dominio"]:
            return f"{nome} fora do domínio"
        mx = c.get("maximo")
        if mx == "momento da carga" and str(v) > momento:
            return f"{nome} no futuro"
        if isinstance(mx, (int, float)) and int(v) > mx:
            return f"{nome} acima do máximo"
        if c.get("unico"):
            if (nome, v) in vistos:
                return f"{nome} repetido (chave repetida)"
    return None


def validar(conjunto, linhas, momento=None):
    """linhas: lista de dicts com as chaves origem/linha/execucao além dos campos.
    Devolve (aceitas, reprovadas[(linha, motivo)])."""
    contrato = carregar_contrato(conjunto)
    momento = momento or comum.agora()
    vistos, aceitas, reprovadas = set(), [], []
    unicos = [c["nome"] for c in contrato["campos"] if c.get("unico")]
    for l in linhas:
        m = motivo(l, contrato, vistos, momento)
        if m:
            reprovadas.append((l, m))
        else:
            for u in unicos:
                vistos.add((u, l[u]))
            aceitas.append(l)
    return aceitas, reprovadas


# ---------------------------------------------------------------- lote do dia 3 e pedidos
def carregar_lote(arquivo=None):
    """Carrega o lote de pedidos por arquivo na camada bronze, como chegou (idempotente por arquivo+linha)."""
    arquivo = arquivo or comum.RAIZ / "dados" / "dia3" / "pedidos_dia3.csv"
    br = bronze.abrir()
    exe = bronze.nova_execucao(br, "lote")
    novas = 0
    for i, r in enumerate(comum.ler_csv(arquivo), start=1):
        cur = br.execute(
            "INSERT OR IGNORE INTO pedidos_lote (arquivo, linha, id, cliente_id, valor_centavos, status, criado_em,"
            " observacao, _carregado_em, _execucao) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (arquivo.name, i, comum.como_int(r["id"]), comum.como_int(r["cliente_id"]), comum.como_int(r["valor_centavos"]),
             r["status"], r["criado_em"], r["observacao"], comum.agora(), exe))
        novas += cur.rowcount
    br.commit()
    br.close()
    return novas


def candidatos_pedidos(br):
    """Todos os pedidos que pedem promoção para a silver: os da bronze, depois os do lote, na ordem de chegada."""
    out = []
    for r in br.execute("SELECT * FROM pedidos ORDER BY id"):
        d = dict(r)
        d.update(origem="pedidos", linha=d["id"], execucao=d["_execucao"])
        out.append(d)
    for r in br.execute("SELECT * FROM pedidos_lote ORDER BY arquivo, linha"):
        d = dict(r)
        d.update(origem=d["arquivo"], execucao=d["_execucao"])
        out.append(d)
    return out


def validar_pedidos(registrar=True):
    """Valida todos os pedidos da bronze (+ lote). Escreve a quarentena e devolve (aceitas, reprovadas)."""
    br = bronze.abrir()
    cand = candidatos_pedidos(br)
    aceitas, reprovadas = validar("pedidos", cand)
    if registrar:
        br.execute("DELETE FROM quarentena WHERE conjunto = 'pedidos'")
        for l, m in reprovadas:
            conteudo = {k: l[k] for k in ("id", "cliente_id", "valor_centavos", "status", "criado_em", "observacao")}
            br.execute("INSERT INTO quarentena VALUES (?,?,?,?,?,?,?)",
                       ("pedidos", l["origem"], l["linha"], json.dumps(conteudo, ensure_ascii=False), m,
                        l["execucao"], comum.agora()))
        br.commit()
    br.close()
    return aceitas, reprovadas


def validar_clientes_navegacao():
    br = bronze.abrir()
    cli = []
    for r in br.execute("SELECT * FROM clientes ORDER BY id"):
        d = bronze.cliente(br, r["id"])
        d.update(origem="clientes", linha=d["id"], execucao=r["_execucao"])
        cli.append(d)
    nav = []
    for r in br.execute("SELECT * FROM navegacao ORDER BY evento_id"):
        d = dict(r)
        d.update(origem="navegacao", linha=d["evento_id"], execucao=d["_execucao"])
        nav.append(d)
    br.close()
    return validar("clientes", cli), validar("navegacao", nav)


def receita_paga(linhas):
    return sum(l["valor_centavos"] for l in linhas if l.get("status") == "pago" and l.get("valor_centavos") is not None)


def resumo_quarentena():
    br = bronze.abrir()
    rows = [dict(r) for r in br.execute("SELECT * FROM quarentena ORDER BY conjunto, origem, linha")]
    br.close()
    return rows
