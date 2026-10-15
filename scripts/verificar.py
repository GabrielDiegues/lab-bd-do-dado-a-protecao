#!/usr/bin/env python3
"""Roda o laboratório inteiro do zero e confere CADA número esperado das Missões 0 a 9.
Gera evidencias/missao0.txt … missao9.txt. Termina com código 1 se qualquer verificação falhar.

Fase A (estado temporário): Missões 0, 1, 2 (cada cenário recomeça do dia 1) e variações da Missão 3.
Fase B (estado real, pasta estado/): o pipeline canônico, Missões 3 a 9, uma etapa depois da outra.
Os termos de busca da Missão 8 nunca são impressos nas evidências (só o rótulo), para a própria evidência
não ser uma morada do titular."""
import contextlib
import json
import os
import pathlib
import re
import secrets
import sqlite3
import subprocess
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import comum  # noqa: E402
from governanca import catalogo, regras, varredor  # noqa: E402
from ingestao import bronze, carga, cdc, fluxo, leitores, origem  # noqa: E402
from privacidade import consumo, eliminacao, esquecer  # noqa: E402
from qualidade import validador  # noqa: E402
from resiliencia import backup, ensaio, reconstruir  # noqa: E402
from seguranca import acesso, cripto, pseudonimo, silver  # noqa: E402

R = comum.reais
FALHAS = []
EVIDENCIAS = []


class Ev:
    def __init__(self, n, titulo):
        self.n, self.linhas = n, [titulo, "=" * len(titulo), ""]

    def txt(self, s=""):
        self.linhas.append(s)

    def checa(self, descr, obtido, esperado):
        ok = obtido == esperado
        self.linhas.append(f"[{'ok' if ok else 'FALHOU'}] {descr}: {obtido}" + ("" if ok else f"   (esperado: {esperado})"))
        if not ok:
            FALHAS.append(f"missão {self.n}: {descr}: obtido {obtido}, esperado {esperado}")
        return ok

    def fecha(self):
        (comum.pasta_evidencias() / f"missao{self.n}.txt").write_text("\n".join(self.linhas) + "\n", encoding="utf-8")


@contextlib.contextmanager
def estado_temporario():
    antigo = os.environ.get("LAB_ESTADO")
    with tempfile.TemporaryDirectory(prefix="lab-bd-") as d:
        os.environ["LAB_ESTADO"] = d
        try:
            yield d
        finally:
            if antigo is None:
                os.environ.pop("LAB_ESTADO", None)
            else:
                os.environ["LAB_ESTADO"] = antigo


def textos_de(banco):
    """Todos os valores de texto de um banco (para a busca de termos)."""
    con = comum.conectar(banco, somente_leitura=True)
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        for linha in con.execute(f"SELECT * FROM {t}"):
            for v in linha:
                if isinstance(v, str):
                    yield f"{banco}.{t}", v
    con.close()


def buscar_termos(termos, bancos=("origem", "leitores", "log", "bronze", "silver", "gold")):
    achados = []
    for b in bancos:
        if not comum.caminho(b).exists():
            continue
        for onde, v in textos_de(b):
            for rot, t in termos.items():
                if t.lower() in v.lower():
                    achados.append((onde, rot))
    return achados


def pii_em_silver():
    """Procura e-mail, CPF, telefone e IP em todos os valores da silver (e nos nomes de coluna proibidos)."""
    ocorrencias, colunas_proibidas = [], []
    con = comum.conectar("silver", somente_leitura=True)
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        for c in con.execute(f"PRAGMA table_info({t})"):
            if c[1] in ("nome", "email", "cpf", "ip", "observacao", "cliente_id", "id_cliente"):
                colunas_proibidas.append(f"{t}.{c[1]}")
        for linha in con.execute(f"SELECT * FROM {t}"):
            for v in linha:
                if isinstance(v, str):
                    for tipo, rx in varredor.PADROES.items():
                        if rx.search(v):
                            ocorrencias.append((t, tipo))
    con.close()
    return ocorrencias, colunas_proibidas


def conjunto_ps():
    con = comum.conectar("silver", somente_leitura=True)
    s = {r[0] for r in con.execute("SELECT cliente_ps FROM clientes")}
    con.close()
    return s


def reinicia(tudo=True):
    comum.zerar_estado()
    origem.iniciar()


# ====================================================================== FASE A
def fase_a():
    # ------------------------------------------------------------ Missão 0
    ev = Ev(0, "Missão 0 · A origem e o repositório")
    with estado_temporario():
        origem.iniciar()
        c = origem.contagens()
        ev.checa("clientes, pedidos e eventos de navegação na origem", (c["clientes"], c["pedidos"], c["navegacao"]), (6, 8, 8))
        ev.checa("receita paga na origem", R(c["receita_paga"]), "R$ 655,00")
        con = comum.conectar("origem", somente_leitura=True)
        fks = con.execute("PRAGMA foreign_key_list(pedidos)").fetchall()
        con.close()
        ev.checa("pedidos sem chave estrangeira (o pedido sobrevive à exclusão do cliente)", len(fks), 0)
    ev.fecha()

    # ------------------------------------------------------------ Missão 1
    ev = Ev(1, "Missão 1 · Carga incremental (marca-d'água, mesclagem e idempotência)")
    with estado_temporario():
        origem.iniciar()
        r1 = carga.executar()
        b = r1["bronze"]
        ev.checa("1ª execução: clientes, pedidos e eventos na bronze", (b["clientes"], b["pedidos"], b["navegacao"]), (6, 8, 8))
        r2 = carga.executar()
        b = r2["bronze"]
        ev.checa("2ª execução, sem mudança na origem: linhas lidas", r2["total_lidas"], 0)
        ev.checa("2ª execução: totais continuam", (b["clientes"], b["pedidos"], b["navegacao"]), (6, 8, 8))
        origem.aplicar_dia2()
        r3 = carga.executar()
        ev.checa("depois das mudanças do dia 2: linhas lidas", r3["total_lidas"], 4)
        ev.checa("  … quais tabelas", r3["lidas"], {"clientes": 2, "pedidos": 2, "navegacao": 0})
        b = r3["bronze"]
        ev.checa("bronze: clientes, pedidos", (b["clientes"], b["pedidos"]), (7, 9))
        ev.checa("bronze: receita paga", R(b["receita_paga"]), "R$ 750,90")
        br = bronze.abrir()
        ev.checa("cliente 5 excluída na origem e ainda na bronze (ponto de partida da Missão 2)",
                 (origem.contagens()["clientes"], br.execute("SELECT COUNT(*) FROM clientes WHERE id=5").fetchone()[0]), (6, 1))
        ev.checa("colunas de controle preenchidas (_carregado_em e _execucao)",
                 br.execute("SELECT COUNT(*) FROM clientes WHERE _carregado_em IS NULL OR _execucao IS NULL").fetchone()[0], 0)
        br.close()
        ev.checa("rodar de novo: 0 linhas", carga.executar()["total_lidas"], 0)
    ev.fecha()

    # ------------------------------------------------------------ Missão 2
    ev = Ev(2, "Missão 2 · Captura de mudanças (Trilha A: tabela `mudancas` + gatilhos)")
    with estado_temporario():
        reinicia()
        carga.executar()
        cdc.ligar_captura()
        origem.aplicar_dia2()
        evs = cdc.eventos()
        ev.checa("o log registra eventos", len(evs), 5)
        ev.checa("na ordem em que foram aplicados (tabela, operação)", [(e["tabela"], e["op"]) for e in evs],
                 [("pedidos", "alteração"), ("clientes", "alteração"), ("clientes", "inserção"), ("pedidos", "inserção"),
                  ("clientes", "exclusão")])
        for e in evs:
            ev.txt(f"   #{e['seq']} {e['op']:10} {e['tabela']:9} chave {e['chave']}")
        n = cdc.sincronizar()
        ev.checa("eventos aplicados na primeira sincronização", n, 5)

        def estado_bronze():
            br = bronze.abrir()
            out = {"clientes": br.execute("SELECT COUNT(*) FROM clientes").fetchone()[0],
                   "pedidos": br.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0],
                   "email3": bronze.cliente(br, 3)["email"],
                   "cliente5": br.execute("SELECT COUNT(*) FROM clientes WHERE id=5").fetchone()[0],
                   "pedido106": br.execute("SELECT COUNT(*) FROM pedidos WHERE id=106").fetchone()[0],
                   "receita": bronze.contagens(br)["receita_paga"]}
            br.close()
            return out
        e1 = estado_bronze()
        ev.checa("bronze: clientes (sem a cliente 5) e pedidos", (e1["clientes"], e1["pedidos"], e1["cliente5"]), (6, 9, 0))
        ev.checa("e-mail novo no cliente 3", e1["email3"], "carla.n@example.com")
        ev.checa("o pedido 106 continua lá", e1["pedido106"], 1)
        ev.checa("receita paga", R(e1["receita"]), "R$ 750,90")
        ev.checa("sincronizar de novo não aplica nada", cdc.sincronizar(), 0)
        ev.checa("reaplicar o log desde o primeiro evento: eventos reaplicados", cdc.sincronizar(desde=0), 5)
        ev.checa("reaplicar desde o primeiro evento: mesmos números", estado_bronze(), e1)
        ev.txt()
        ev.txt("Trilha A (sem infraestrutura): gatilhos AFTER INSERT/UPDATE/DELETE gravam em `mudancas` na mesma transação")
        ev.txt("da mudança; a exclusão leva só a chave. Motivo no README.")
    ev.fecha()


# ====================================================================== cenários da Missão 3
def cenario_fluxo(modo):
    """Roda o tópico de navegação num estado temporário. Devolve (linhas_do_tempo, resumo)."""
    with estado_temporario():
        reinicia()
        carga.executar(("clientes", "pedidos"))
        info = {}
        if modo == "normal":
            linhas = fluxo.demo_simulada()
        elif modo == "queda":
            linhas = fluxo.demo_simulada(derrubar_visitas_apos=4)
        elif modo == "queda_antes_de_salvar":
            linhas = []
            for ev_ in fluxo.eventos_a_publicar():
                fluxo.publicar(ev_)
            n1, _ = fluxo.passo("visitas", derrubar_apos=4, salvar_ultimo=False)
            info["offset_salvo_na_queda"] = leitores.pos("visitas", fluxo.TOPICO)
            n2, _ = fluxo.passo("visitas")
            info["processados_antes"], info["processados_depois"] = n1, n2
            fluxo.passo("bronze")
        con = leitores.abrir()
        info["eventos_contados"] = con.execute("SELECT COUNT(*) FROM visitas_eventos").fetchone()[0]
        con.close()
        info["visitas"] = fluxo.visitas_por_pagina()
        br = bronze.abrir()
        info["bronze_nav"] = br.execute("SELECT COUNT(*) FROM navegacao").fetchone()[0]
        info["bronze_nav_distintos"] = br.execute("SELECT COUNT(DISTINCT evento_id) FROM navegacao").fetchone()[0]
        br.close()
        return linhas, info


ESPERADO_VISITAS = {"/carrinho": 2, "/home": 1, "/produto/camiseta": 1, "/produto/fone": 1, "/produto/mochila": 1,
                    "/produto/relogio": 1, "/produto/tenis": 1}


def missao3_variacoes(ev):
    linhas, info = cenario_fluxo("normal")
    ev.txt("Cenário 1 · sem queda (1 evento por segundo; a bronze acorda a cada 5 s)")
    for t, h, lv, lb in linhas:
        ev.txt(f"   t={t}s  publicado até o offset {h}  | leitor rápido atrás: {lv}  | bronze atrás: {lb}")
    ev.checa("leitor rápido sempre no último evento", max(l[2] for l in linhas), 0)
    ev.checa("bronze fica até 5 eventos atrás", max(l[3] for l in linhas) <= 5 and max(l[3] for l in linhas) > 0, True)
    ev.checa("visitas por página ao fim", info["visitas"], ESPERADO_VISITAS)
    ev.checa("bronze: eventos (sem duplicata)", (info["bronze_nav"], info["bronze_nav_distintos"]), (8, 8))

    linhas, info = cenario_fluxo("queda")
    ev.txt()
    ev.txt("Cenário 2 · `visitas` cai depois do 4º evento (offset salvo) e volta quando o produtor termina")
    for t, h, lv, lb in linhas:
        ev.txt(f"   t={t}s  publicado até o offset {h}  | visitas atrás: {lv}  | bronze atrás: {lb}")
    ev.checa("o atraso de um não segura o outro (bronze segue normal)", max(l[3] for l in linhas) <= 5, True)
    ev.checa("visitas depois da religação: mesmos totais", info["visitas"], ESPERADO_VISITAS)
    ev.checa("nenhum evento contado duas vezes (eventos contados)", info["eventos_contados"], 8)

    _, info = cenario_fluxo("queda_antes_de_salvar")
    ev.txt()
    ev.txt("Cenário 3 · queda ENTRE processar e salvar o offset (entrega pelo menos uma vez)")
    ev.checa("offset salvo na queda (processou 4, salvou 3)", info["offset_salvo_na_queda"], 3)
    ev.checa("ao voltar, relê o 4º evento: processados antes e depois", (info["processados_antes"], info["processados_depois"]), (4, 5))
    ev.checa("mesmo assim, cada evento é contado uma vez só", info["eventos_contados"], 8)
    ev.checa("totais por página iguais", info["visitas"], ESPERADO_VISITAS)
    ev.txt()
    ev.txt("Decisão: o offset é salvo DEPOIS de processar. A queda no meio repete um evento (nunca perde) e o")
    ev.txt("processamento idempotente (INSERT OR IGNORE pela chave do evento) impede a contagem dupla.")


# ====================================================================== FASE B
def fase_b():
    comum.zerar_estado()
    if eliminacao.ARQUIVO.exists():
        eliminacao.ARQUIVO.unlink()
    resultados = {}

    # ------------------------------------------------------------ Missão 3
    ev = Ev(3, "Missão 3 · Um log, vários leitores (tópico `navegacao`)")
    regras.verificar()
    origem.iniciar()
    carga.executar(("clientes", "pedidos"))  # a carga em lote da navegação sai de cena
    cdc.ligar_captura()
    n_cifrados = cripto.proteger_bronze()  # EXTRA da Missão 8, ligado desde o dia 1: assim a cópia de segurança já nasce cifrada
    missao3_variacoes(ev)
    ev.txt()
    ev.txt("Cenário canônico (estado real do pipeline)")
    linhas = fluxo.demo_simulada()
    ev.checa("visitas por página", fluxo.visitas_por_pagina(), ESPERADO_VISITAS)
    br = bronze.abrir()
    ev.checa("bronze: 8 eventos, sem duplicata", (br.execute("SELECT COUNT(*) FROM navegacao").fetchone()[0],
                                                 br.execute("SELECT COUNT(DISTINCT evento_id) FROM navegacao").fetchone()[0]), (8, 8))
    br.close()
    fluxo.passo("por_cliente")  # leitor novo, ligado depois de tudo
    ev.checa("leitor novo `por_cliente` (desde o offset 0): eventos por cliente (None = visitante)",
             fluxo.eventos_por_cliente(), {1: 2, 5: 2, 2: 1, 3: 1, 6: 1, None: 1})
    ev.checa("depois de todos lerem, o log continua com os eventos", fluxo.eventos_no_log(), 8)
    ev.checa("offsets próprios de cada leitor",
             {l: leitores.pos(l, fluxo.TOPICO) for l in ("visitas", "bronze", "por_cliente")},
             {"visitas": 8, "bronze": 8, "por_cliente": 8})
    ev.fecha()

    # ------------------------------------------------------------ cópia de segurança do dia 1 (Missão 9)
    info_backup = backup.criar("dia1")
    resultados["backup"] = info_backup

    # ------------------------------------------------------------ dia 2 por captura de mudanças
    origem.aplicar_dia2()
    assert cdc.sincronizar() == 5

    # ------------------------------------------------------------ Missão 4
    ev = Ev(4, "Missão 4 · Contrato, validação e quarentena")
    novas = validador.carregar_lote()
    ev.checa("linhas do lote do dia 3 na bronze", novas, 7)
    aceitas, reprovadas = validador.validar_pedidos()
    do_lote_ok = [l for l in aceitas if l["origem"] != "pedidos"]
    ev.checa("do lote: aceitas (pedidos 110 e 115)", sorted(l["id"] for l in do_lote_ok), [110, 115])
    ev.checa("do lote: em quarentena", len(reprovadas), 5)
    for l, m in reprovadas:
        ev.txt(f"   pedido {l['id']} (arquivo {l['origem']}, linha {l['linha']}, execução {l['execucao']}): {m}")
    ev.checa("5 motivos diferentes", len({m for _, m in reprovadas}), 5)
    ev.checa("motivos",
             sorted(m for _, m in reprovadas),
             sorted(["valor_centavos negativo", "cliente_id ausente", "status fora do domínio",
                     "id repetido (chave repetida)", "criado_em no futuro"]))
    (cl_ok, cl_rep), (nv_ok, nv_rep) = validador.validar_clientes_navegacao()
    ev.checa("contratos de clientes e navegação: reprovadas", (len(cl_rep), len(nv_rep)), (0, 0))
    s = silver.construir(generalizar=False)
    ev.checa("silver: pedidos", s["pedidos"], 11)
    ev.checa("silver: receita paga", R(s["receita_paga"]), "R$ 844,90")
    todos = validador.candidatos_pedidos(bronze.abrir())
    ev.checa("sem a validação, o mesmo cálculo daria", R(validador.receita_paga(todos)), "R$ 932,90")
    ev.checa("quarentena persistida na bronze", len([q for q in validador.resumo_quarentena() if q["conjunto"] == "pedidos"]), 5)
    ev.txt("Regras lidas de contratos/*.yaml (obrigatorio, minimo, dominio, maximo, unico), não fixas no código.")
    ev.fecha()

    # ------------------------------------------------------------ Missão 5
    ev = Ev(5, "Missão 5 · Governança: acordo, catálogo, regra como código e varredor")
    acordo_txt = (comum.RAIZ / "governanca" / "acordo.yaml").read_text(encoding="utf-8")
    quebrado = acordo_txt.replace("prazo: 6 meses\n", "prazo: ...\n")
    assert quebrado != acordo_txt
    env = dict(os.environ)
    try:
        (comum.RAIZ / "governanca" / "acordo.yaml").write_text(quebrado, encoding="utf-8")
        p = subprocess.run([sys.executable, str(RAIZ / "lab.py"), "regras"], capture_output=True, text=True, env=env)
        ev.checa("sem a retenção de `navegacao`, o pipeline para (código de saída)", p.returncode, 2)
        ev.checa("mensagem clara", "navegacao: conjunto de classe 'pessoal' sem retenção definida" in p.stdout, True)
        ev.txt("   " + p.stdout.strip().replace("\n", "\n   "))
    finally:
        (comum.RAIZ / "governanca" / "acordo.yaml").write_text(acordo_txt, encoding="utf-8")
    p = subprocess.run([sys.executable, str(RAIZ / "lab.py"), "regras"], capture_output=True, text=True, env=env)
    ev.checa("devolvido o prazo, o pipeline passa", p.returncode, 0)

    rascunho = varredor.classes_declaradas()
    rascunho[("pedidos", "observacao")] = "interno"
    rascunho[("navegacao", "ip")] = "interno"
    achados = {(a["tabela"], a["coluna"]): a for a in varredor.varrer(classes=rascunho) if a["escondido"]}
    ev.txt()
    ev.txt("Varredor sobre o rascunho (observacao e ip declarados como `interno`):")
    for a in achados.values():
        ev.txt(f"   NÃO DECLARADO {a['tabela']}.{a['coluna']}: {a['tipos']} em {len(a['ids'])} linhas (chaves {a['ids']})")
    ev.checa("dado pessoal onde ninguém declarou", sorted(achados), [("navegacao", "ip"), ("pedidos", "observacao")])
    ev.checa("pedidos com dado pessoal em observacao (104 e 106)", achados[("pedidos", "observacao")]["ids"], [104, 106])
    ev.checa("coluna ip: eventos", len(achados[("navegacao", "ip")]["ids"]), 8)
    final = [a for a in varredor.varrer() if a["escondido"]]
    ev.checa("com a classificação final dos contratos: nada fica de fora do mapa", final, [])

    cat1 = catalogo.gerar()
    ct_arq = comum.RAIZ / "contratos" / "clientes.yaml"
    ct_txt = ct_arq.read_text(encoding="utf-8")
    try:
        ct_arq.write_text(ct_txt.replace("Cadastro de quem compra na loja.", "Cadastro de quem compra na loja (descrição de teste)."),
                          encoding="utf-8")
        cat2 = catalogo.gerar()
    finally:
        ct_arq.write_text(ct_txt, encoding="utf-8")
    catalogo.gerar()
    ev.checa("mudar a descrição no contrato muda o catálogo sem editá-lo", "(descrição de teste)" in cat2 and "(descrição de teste)" not in cat1, True)
    ev.fecha()

    # ------------------------------------------------------------ Missão 6
    ev = Ev(6, "Missão 6 · Segurança: matriz, pseudônimo, silver e trajeto do CPF")
    silver.construir(generalizar=False)
    ocorr, proibidas = pii_em_silver()
    ev.checa("silver: e-mail, CPF, telefone ou IP em qualquer valor", ocorr, [])
    ev.checa("silver: colunas proibidas (nome, email, cpf, ip, observacao, cliente_id)", proibidas, [])
    bruto = comum.caminho("silver").read_bytes().decode("latin-1")
    ev.checa("silver: e-mail, CPF, telefone ou IP nos bytes do arquivo (inclusive páginas livres)",
             [t for t, rx in varredor.PADROES.items() if rx.search(bruto)], [])
    ps1 = conjunto_ps()
    silver.construir(generalizar=False)
    ps2 = conjunto_ps()
    ev.checa("duas execuções com a mesma chave: mesmos pseudônimos", ps1 == ps2 and len(ps1) == 6, True)
    ps3 = {pseudonimo.pseudonimo(i, secrets.token_hex(32)) for i in (1, 2, 3, 4, 6, 7)}
    ev.checa("com outra chave: nenhum pseudônimo se repete", len(ps1 & ps3), 0)
    resultados["ps_missao6"] = ps1
    ev.txt("   pseudônimos (12 primeiros hex, sem o id): " + ", ".join(sorted(p[:12] for p in ps1)))
    con = comum.conectar("silver", somente_leitura=True)
    ev.checa("a junção pedidos × clientes funciona pelo mesmo pseudônimo",
             con.execute("SELECT COUNT(*) FROM pedidos p JOIN clientes c ON c.cliente_ps = p.cliente_ps").fetchone()[0] > 0, True)
    con.close()
    # papéis
    try:
        acesso.abrir("analista", "bronze")
        pode = True
    except PermissionError:
        pode = False
    ev.checa("analista lê a bronze?", pode, False)
    an = acesso.abrir("analista", "silver")
    try:
        an.execute("DELETE FROM pedidos")
        grava = True
    except sqlite3.OperationalError:
        grava = False
    an.close()
    ev.checa("analista escreve na silver?", grava, False)
    acesso.abrir("pipeline", "bronze").close()
    ev.checa("pipeline lê a bronze", True, True)
    trilha = [json.loads(l) for l in (comum.estado() / "auditoria.log").read_text().splitlines()]
    ev.checa("trilha de leitura registra os três acessos, inclusive o negado", [t["resultado"] for t in trilha][-3:], ["negado", "leitura", "escrita"])

    # extra: pipeline inteiro com dados sintéticos, sem tocar na loja
    with estado_temporario():
        origem.iniciar(comum.RAIZ / "dados" / "sintetico")
        carga.executar(("clientes", "pedidos"))
        cdc.ligar_captura()
        fluxo.demo_simulada()
        s2 = silver.construir(generalizar=True)
        g2 = consumo.construir_gold(k=2)
        ev.checa("EXTRA · pipeline do início ao fim com dados sintéticos (clientes, pedidos, eventos na silver)",
                 (s2["clientes"], s2["pedidos"], s2["navegacao"]), (6, 8, 8))
        con = comum.conectar("origem", somente_leitura=True)
        reais_ = con.execute("SELECT COUNT(*) FROM clientes WHERE nome LIKE '%Lima%' OR cpf LIKE '111.%'").fetchone()[0]
        con.close()
        ev.checa("EXTRA · nenhuma pessoa real nos dados sintéticos", reais_, 0)
    ev.checa("EXTRA · a origem da loja não foi tocada", origem.contagens()["clientes"], 6)
    ev.txt()
    ev.txt("A chave (CHAVE_PSEUDONIMO) vem do ambiente; a busca pelo valor dela no repositório é feita no fim (ver abaixo).")
    resultados["ev6"] = ev

    # ------------------------------------------------------------ Missão 7
    ev = Ev(7, "Missão 7 · Privacidade: minimização, K-anonimato e visão de consumo")
    cdecl = []
    for conj in ("clientes",):
        ct = validador.carregar_contrato(conj)
        cdecl = {c["nome"]: c for c in ct["campos"]}
    ev.checa("finalidade registrada para cada campo pessoal que restou na silver (nascimento, cidade, id→cliente_ps)",
             all(cdecl[c].get("finalidade") for c in ("nascimento", "cidade", "id")), True)
    ev.checa("campos sem finalidade saem da silver (nome, e-mail, CPF)",
             [c for c in ("nome", "email", "cpf") if not cdecl[c].get("finalidade")], ["nome", "email", "cpf"])
    silver.construir(generalizar=False)
    k0 = consumo.medir_k("nascimento")
    ev.checa("com a data de nascimento completa: combinações com uma pessoa só", (k0["unicas"], k0["combinacoes"]), (6, 6))
    silver.construir(generalizar=True)
    k1 = consumo.medir_k()
    ev.checa("faixa etária + cidade: combinações com uma pessoa só", k1["unicas"], 4)
    ev.txt("   grupos (cidade, faixa): " + str(dict(sorted((f"{c}/{f}", n) for (c, f), n in k1["grupos"].items()))))
    g = consumo.construir_gold(k=2)
    por = {l["cidade"]: l for l in g["linhas"]}
    ev.checa("K=2 · Santos", (R(por["Santos"]["receita_centavos"]), por["Santos"]["clientes"]), ("R$ 545,00", 3))
    ev.checa("K=2 · Sorocaba", (R(por["Sorocaba"]["receita_centavos"]), por["Sorocaba"]["clientes"]), ("R$ 95,90", 2))
    ev.checa("K=2 · Campinas suprimida", (por["Campinas"]["suprimida"], por["Campinas"]["receita_centavos"], por["Campinas"]["clientes"]), (1, None, 1))
    ev.checa("total geral (inclui a cidade suprimida e o pedido 106, sem cadastro)", R(g["total"]), "R$ 844,90")
    g3 = {l["cidade"]: l for l in consumo.construir_gold(k=3)["linhas"]}
    ev.checa("K=3 · Sorocaba também é suprimida", (g3["Sorocaba"]["suprimida"], g3["Santos"]["suprimida"]), (1, 0))
    g = consumo.construir_gold(k=2)
    resultados["gold_antes"] = g
    ev.fecha()

    # ------------------------------------------------------------ Missão 8
    ev = Ev(8, "Missão 8 · Esquecer de verdade (cliente 5)")
    termos = {"nome": "Elisa", "CPF": "555.555.555-55", "telefone": "(13) 90000-0005", "IP": "203.0.113.55",
              "e-mail": "elisa.moura@example.com"}
    antes = buscar_termos(termos)
    ev.checa("ANTES: onde a titular ainda aparece nas camadas vivas (o cadastro já saiu pelo log na Missão 2)",
             sorted({r for _, r in antes}), ["IP", "telefone"])
    ev.txt("   moradas vivas: " + ", ".join(sorted({o for o, _ in antes})))
    ev.checa("EXTRA · crypto-shredding: cadastros cifrados com chave própria na carga do dia 1", n_cifrados, 6)
    pasta_dia1 = comum.pasta_backup() / "dia1"
    cb = sqlite3.connect(f"file:{pasta_dia1 / 'bronze.db'}?mode=ro", uri=True)
    blob5 = cb.execute("SELECT email FROM clientes WHERE id = 5").fetchone()[0]
    cb.close()
    ev.checa("a cópia do dia 1 guarda o cadastro dela CIFRADO (nenhum dado em claro)", blob5.startswith(cripto.PREFIXO), True)
    ev.checa("ANTES de esquecer: com a chave dela, a cópia abre", cripto.revelar(5, blob5), termos["e-mail"])
    br = bronze.abrir()
    ev.checa("com a chave, o cadastro vivo abre", bronze.cliente(br, 3)["email"], "carla.n@example.com")
    br.close()
    snap = resultados["gold_antes"]

    esquecer.esquecer(5)
    depois = buscar_termos(termos)
    ev.checa("DEPOIS: ocorrências na origem, no log, nos leitores, na bronze, na silver e na gold (busca por valor)", depois, [])
    resq = esquecer.buscar_resquicios(["elisa", "555.555.555-55", "(13) 90000-0005", "203.0.113.55"])
    ev.checa("DEPOIS: resquícios nos bytes dos arquivos de banco (páginas livres incluídas)", resq, {})
    ev.checa("EXTRA · a cópia de segurança do dia 1 virou ruído para ela (a chave foi apagada)",
             (cripto.chave_do_titular(5), cripto.revelar(5, blob5)), (None, None))

    con = comum.conectar("origem", somente_leitura=True)
    nav_o = con.execute("SELECT COUNT(*) FROM navegacao").fetchone()[0]
    obs106 = con.execute("SELECT observacao FROM pedidos WHERE id=106").fetchone()[0]
    existe106 = con.execute("SELECT COUNT(*) FROM pedidos WHERE id=106").fetchone()[0]
    con.close()
    br = bronze.abrir()
    cont = bronze.contagens(br)
    br.close()
    sv = comum.conectar("silver", somente_leitura=True)
    sil = {"navegacao": sv.execute("SELECT COUNT(*) FROM navegacao").fetchone()[0],
           "pedidos": sv.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0],
           "receita": sv.execute("SELECT SUM(valor_centavos) FROM pedidos WHERE status='pago'").fetchone()[0],
           "ps106": sv.execute("SELECT cliente_ps FROM pedidos WHERE id=106").fetchone()[0]}
    sv.close()
    ev.checa("eventos de navegação (origem, bronze, silver)", (nav_o, cont["navegacao"], sil["navegacao"]), (6, 6, 6))
    ev.checa("pedidos na silver", sil["pedidos"], 11)
    ev.checa("receita paga na silver", R(sil["receita"]), "R$ 844,90")
    ev.checa("a visão de consumo não muda", consumo.ler_gold(), snap)
    ev.checa("pedido 106 fica: existe, observação limpa, cliente_ps vazio", (existe106, obs106, sil["ps106"]), (1, None, None))
    ev.checa("visitas por página: /carrinho perde o evento dela", fluxo.visitas_por_pagina().get("/carrinho"), 1)
    ev.checa("estado do leitor por_cliente sem a titular", 5 in fluxo.eventos_por_cliente(), False)
    log = fluxo.abrir_log()
    ev.checa("tópico navegacao: lápides e cargas ainda legíveis da titular",
             (log.execute("SELECT COUNT(*) FROM topico_navegacao WHERE lapide=1").fetchone()[0],
              log.execute("SELECT COUNT(*) FROM topico_navegacao WHERE chave='5' AND lapide=0 AND valor IS NOT NULL").fetchone()[0]),
             (1, 0))
    log.close()
    lista = eliminacao.ler()
    ev.checa("lista de eliminação: registros", len(lista), 1)
    texto_lista = json.dumps(lista, ensure_ascii=False)
    ev.checa("lista sem nome, CPF, e-mail ou telefone",
             [r for r, t in termos.items() if t.lower() in texto_lista.lower()] + [t for t, rx in varredor.PADROES.items() if rx.search(texto_lista)], [])
    assinatura = (json.dumps(consumo.ler_gold(), sort_keys=True), json.dumps(lista, sort_keys=True), json.dumps(bronze.contagens(), sort_keys=True))
    esquecer.esquecer(5)
    lista2 = eliminacao.ler()
    assinatura2 = (json.dumps(consumo.ler_gold(), sort_keys=True), json.dumps(lista2, sort_keys=True), json.dumps(bronze.contagens(), sort_keys=True))
    ev.checa("rodar `esquecer 5` de novo não falha nem muda nada (visão de consumo, lista e contagens iguais)", assinatura2 == assinatura, True)
    ev.txt()
    ev.txt("Moradas tratadas (ver privacidade/moradas.md):")
    for m in lista[0]["moradas"]:
        ev.txt("   - " + m)
    resultados["ev8"] = ev  # os arquivos de texto são varridos no final, depois que todas as evidências existirem

    # ------------------------------------------------------------ Missão 9
    ev = Ev(9, "Missão 9 · Resiliência: cópias, ensaio e RTO medido")
    pasta = comum.pasta_backup() / "dia1"
    iso = comum.pasta_cofre() / "copia_isolada" / "dia1"
    ev.checa("cópia 2 (outra pasta, fora do repositório): erros no teste de integridade", backup.verificar(pasta), [])
    ev.checa("cópia 3 (isolada, somente leitura): erros no teste de integridade", backup.verificar(iso), [])
    try:
        (iso / "bronze.db").open("ab").close()
        escreve = True
    except PermissionError:
        escreve = False
    ev.checa("a cópia isolada aceita escrita? (imutável no laboratório)", escreve, False)
    ev.checa("backup e cofre ficam fora do repositório", (str(pasta).startswith(str(RAIZ)), str(iso).startswith(str(RAIZ))), (False, False))
    ev.checa("cópia da chave guardada em outro lugar", (comum.pasta_cofre() / "chave_pseudonimo.txt").read_text() == pseudonimo.chave(), True)
    ev.txt(f"   offsets guardados com a cópia: {resultados['backup']['offsets']}")
    expected = {"clientes": 6, "pedidos": 11, "navegacao": 6, "receita": 84490}

    def numeros():
        sv = comum.conectar("silver", somente_leitura=True)
        out = {"clientes": sv.execute("SELECT COUNT(*) FROM clientes").fetchone()[0],
               "pedidos": sv.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0],
               "navegacao": sv.execute("SELECT COUNT(*) FROM navegacao").fetchone()[0],
               "receita": sv.execute("SELECT SUM(valor_centavos) FROM pedidos WHERE status='pago'").fetchone()[0]}
        sv.close()
        return out

    ensaios = {}
    for rotulo, isolada in (("cópia local", False), ("cópia isolada", True)):
        r = ensaio.ensaiar("dia1", da_isolada=isolada)
        ensaios[rotulo] = r
        ev.txt()
        ev.txt(f"Ensaio com a {rotulo}:")
        for txt, t, extra in r["etapas"]:
            ev.txt(f"   {t:6.2f}s  {txt}  {extra}")
        ev.checa(f"[{rotulo}] a cópia do dia 1 continha a cliente 5", r["tem_cliente_5"], True)
        ev.checa(f"[{rotulo}] depois do ensaio: clientes, pedidos, eventos, receita", numeros(), expected)
        ev.checa(f"[{rotulo}] a visão de consumo é a mesma", consumo.ler_gold(), snap)
        ev.checa(f"[{rotulo}] a cliente 5 não reaparece em nenhuma camada", buscar_termos(termos), [])
        ev.checa(f"[{rotulo}] nem nos bytes dos bancos", esquecer.buscar_resquicios(["elisa", "555.555.555-55", "(13) 90000-0005", "203.0.113.55"]), {})
    rto = max(r["segundos"] for r in ensaios.values())
    ev.txt()
    ev.txt(f"RTO medido no ensaio: {rto:.2f} s (pior dos dois). Prometido no plano (bronze + silver): 2 h.")
    ev.txt("A diferença é enorme porque o laboratório tem 25 linhas; o número que importa é o método:")
    ev.txt("cronometrar a restauração completa, comparar com a promessa e registrar a diferença.")
    resultados["rto"] = rto

    # extra: outra chave
    ps_ok = conjunto_ps()
    ev.checa("EXTRA · a reconstrução com a chave correta reproduz os pseudônimos da Missão 6", ps_ok == resultados["ps_missao6"], True)
    reconstruir.reconstruir(chave=secrets.token_hex(32))
    ps_outra = conjunto_ps()
    ev.checa("EXTRA · reconstruir com OUTRA chave: pseudônimos que batem com a evidência da Missão 6",
             len(ps_outra & resultados["ps_missao6"]), 0)
    ev.txt("   Por isso a chave entra no plano: dado restaurado sem a chave certa não liga com nada.")
    reconstruir.reconstruir()
    ev.checa("EXTRA · de volta à chave correta", conjunto_ps() == resultados["ps_missao6"], True)
    ev.fecha()

    # fecha a evidência 6 e 8 (feitas antes para poder ser varridas)
    resultados["ev6"].fecha()
    resultados["ev8"].fecha()
    return termos


def fase_final(termos):
    """Verificações que só fazem sentido com tudo pronto: chave fora do repositório e termos fora dos documentos."""
    ev6_arq = comum.pasta_evidencias() / "missao6.txt"
    chave = pseudonimo.chave()
    achou = []
    for p in RAIZ.rglob("*"):
        if p.is_file() and ".git/" not in str(p) + "/" and "__pycache__" not in str(p):
            try:
                if chave.encode() in p.read_bytes():
                    achou.append(str(p.relative_to(RAIZ)))
            except OSError:
                pass
    linhas = [f"[{'ok' if not achou else 'FALHOU'}] valor da CHAVE_PSEUDONIMO encontrado no repositório inteiro (código, evidências, estado/): {achou or 'nenhuma ocorrência'}"]
    if achou:
        FALHAS.append(f"missão 6: chave no repositório: {achou}")
    with open(ev6_arq, "a", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")

    # termos da titular fora de evidências, documentos e saídas (não de dados/ nem de scripts/)
    achados = []
    for pasta in ("evidencias", "privacidade", "governanca", "seguranca", "resiliencia", "arquitetura", "contratos", "ingestao", "qualidade"):
        for p in (RAIZ / pasta).rglob("*"):
            if p.is_file() and p.suffix in (".md", ".txt", ".json", ".svg", ".yaml", ".py"):
                txt = p.read_text(encoding="utf-8", errors="ignore").lower()
                for rot, t in termos.items():
                    if t.lower() in txt and p.name != "missao8.txt":
                        achados.append((str(p.relative_to(RAIZ)), rot))
    linhas = [f"[{'ok' if not achados else 'FALHOU'}] termos da titular (nome, CPF, telefone, IP, e-mail) em evidências, documentos e código: {achados or 'nenhuma ocorrência'}"]
    if achados:
        FALHAS.append(f"missão 8: termos em arquivos: {achados}")
    with open(comum.pasta_evidencias() / "missao8.txt", "a", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n(os dados de partida em dados/dia1 são o laboratório fictício e ficam de fora da busca)\n")


def main():
    if not os.environ.get("CHAVE_PSEUDONIMO"):
        os.environ["CHAVE_PSEUDONIMO"] = secrets.token_hex(32)
        print("(CHAVE_PSEUDONIMO não estava definida: usando uma chave aleatória só desta execução)")
    fase_a()
    termos = fase_b()
    fase_final(termos)
    if FALHAS:
        print("\nFALHAS:")
        for f in FALHAS:
            print(" -", f)
        sys.exit(1)
    print("Todas as verificações das Missões 0 a 9 passaram. Evidências em evidencias/.")


if __name__ == "__main__":
    main()
