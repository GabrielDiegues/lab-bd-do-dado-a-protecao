#!/usr/bin/env python3
"""CLI única do laboratório. Exemplos:

  export CHAVE_PSEUDONIMO=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
  python3 lab.py tudo            # pipeline do zero, até a visão de consumo
  python3 lab.py esquecer 5      # direito de ser esquecido
  python3 lab.py reconstruir     # recria silver e gold a partir da bronze
  python3 lab.py verificar       # roda tudo e confere cada número esperado (gera evidencias/)
"""
import argparse
import json
import subprocess
import sys

import comum


def _p(txt=""):
    print(txt)


def cmd_origem_init(a):
    from ingestao import origem
    origem.iniciar()
    _p(f"origem no dia 1: {origem.contagens()}")


def cmd_carga(a):
    from ingestao import carga
    tabelas = ("clientes", "pedidos", "navegacao") if a.com_navegacao else ("clientes", "pedidos")
    r = carga.executar(tabelas)
    _p(f"execução {r['execucao']}: leu {r['lidas']} (total {r['total_lidas']}); bronze {r['bronze']}")


def cmd_dia2(a):
    from ingestao import origem
    _p("mudanças do dia 2 aplicadas" if origem.aplicar_dia2() else "dia 2 já estava aplicado")


def cmd_captura(a):
    from ingestao import cdc
    cdc.ligar_captura()
    _p("captura de mudanças ligada (gatilhos em clientes e pedidos)")


def cmd_sincronizar(a):
    from ingestao import cdc
    _p(f"{cdc.sincronizar(desde=0 if a.do_zero else None)} eventos aplicados na bronze")


def cmd_fluxo(a):
    from ingestao import fluxo
    if a.tempo_real:
        fluxo.demo_tempo_real(escala=a.escala)
    else:
        fluxo.demo_simulada(verboso=lambda l: _p("t=%d cabeça=%d atraso(visitas)=%d atraso(bronze)=%d" % l))
    _p(f"visitas por página: {fluxo.visitas_por_pagina()}")
    _p(f"bronze: {fluxo.bronze.contagens()}")


def cmd_leitor_novo(a):
    from ingestao import fluxo
    fluxo.passo("por_cliente")
    _p(f"eventos por cliente: {fluxo.eventos_por_cliente()}")


def cmd_lote(a):
    from qualidade import validador
    _p(f"{validador.carregar_lote()} linhas novas do lote do dia 3 na bronze")


def cmd_validar(a):
    from qualidade import validador
    ok, rep = validador.validar_pedidos()
    _p(f"pedidos: {len(ok)} aceitos, {len(rep)} em quarentena")
    for l, m in rep:
        _p(f"  pedido {l['id']} ({l['origem']}, linha {l['linha']}): {m}")


def cmd_regras(a):
    from governanca import regras
    try:
        regras.verificar()
    except regras.RegraViolada as e:
        _p("PIPELINE PARADO pela regra de governança:\n" + str(e))
        sys.exit(2)
    _p("regras de governança: ok")


def cmd_catalogo(a):
    from governanca import catalogo
    catalogo.gerar()
    _p("governanca/catalogo.md gerado")


def cmd_varredor(a):
    from governanca import varredor
    for r in varredor.varrer():
        marca = "NÃO DECLARADO" if r["escondido"] else "declarado"
        _p(f"{marca:14} {r['tabela']}.{r['coluna']}: {r['tipos']} em {len(r['ids'])} linhas")


def cmd_silver(a):
    from seguranca import silver
    _p(f"silver: {silver.construir(generalizar=not a.com_data)}")


def cmd_gold(a):
    from privacidade import consumo
    g = consumo.construir_gold(k=a.k)
    for l in g["linhas"]:
        r = "suprimida" if l["suprimida"] else comum.reais(l["receita_centavos"])
        _p(f"  {l['cidade']:10} {l['clientes']} cliente(s)  {r}")
    _p(f"  total geral {comum.reais(g['total'])}")


def cmd_proteger(a):
    from seguranca import cripto
    _p(f"{cripto.proteger_bronze()} cadastros cifrados com chave própria (crypto-shredding ativo)")


def cmd_esquecer(a):
    from privacidade import esquecer
    for m in esquecer.esquecer(a.id):
        _p("  tratada: " + m)


def cmd_reconstruir(a):
    from resiliencia import reconstruir
    r = reconstruir.reconstruir()
    _p(f"silver {r['silver']} em {r['segundos']:.2f}s")


def cmd_backup(a):
    from resiliencia import backup
    r = backup.criar(a.nome)
    _p(f"cópia em {r['pasta']}\ncópia isolada (somente leitura) em {r['isolada']}\noffsets {r['offsets']}")


def cmd_ensaio(a):
    from resiliencia import ensaio
    r = ensaio.ensaiar(a.nome)
    for txt, t, extra in r["etapas"]:
        _p(f"  {t:7.2f}s  {txt}  {extra}")
    _p(f"RTO medido: {r['segundos']:.2f}s")


def cmd_tudo(a):
    """Pipeline do zero: origem -> carga -> captura -> fluxo -> dia 2 -> CDC -> lote -> silver -> gold."""
    from ingestao import carga, cdc, fluxo, origem
    from governanca import regras
    from privacidade import consumo
    from qualidade import validador
    from resiliencia import backup
    from seguranca import cripto, pseudonimo, silver
    pseudonimo.chave()
    regras.verificar()
    comum.zerar_estado()
    origem.iniciar()
    carga.executar(("clientes", "pedidos"))
    cdc.ligar_captura()
    cripto.proteger_bronze()  # crypto-shredding desde o dia 1: a cópia de segurança já nasce cifrada
    fluxo.demo_simulada()
    fluxo.passo("por_cliente")
    backup.criar("dia1")
    origem.aplicar_dia2()
    cdc.sincronizar()
    validador.carregar_lote()
    s = silver.construir(generalizar=True)
    g = consumo.construir_gold()
    _p(f"silver {s}")
    for l in g["linhas"]:
        _p("  %-9s %d cliente(s)  %s" % (l["cidade"], l["clientes"],
                                         "suprimida" if l["suprimida"] else comum.reais(l["receita_centavos"])))
    _p(f"total geral {comum.reais(g['total'])}")


def cmd_verificar(a):
    sys.exit(subprocess.call([sys.executable, str(comum.RAIZ / "scripts" / "verificar.py")]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)

    def novo(nome, fn, ajuda, *args):
        p = sp.add_parser(nome, help=ajuda)
        for flags, kw in args:
            p.add_argument(*flags, **kw)
        p.set_defaults(fn=fn)

    novo("origem-init", cmd_origem_init, "recria a origem no dia 1")
    novo("carga", cmd_carga, "carga incremental para a bronze", (["--com-navegacao"], {"action": "store_true"}))
    novo("dia2", cmd_dia2, "aplica as mudanças do dia 2 na origem")
    novo("captura", cmd_captura, "liga os gatilhos de captura de mudanças")
    novo("sincronizar", cmd_sincronizar, "aplica o log de mudanças na bronze", (["--do-zero"], {"action": "store_true"}))
    novo("fluxo", cmd_fluxo, "tópico navegacao com leitor rápido e leitor lento",
         (["--tempo-real"], {"action": "store_true"}), (["--escala"], {"type": float, "default": 1.0}))
    novo("leitor-novo", cmd_leitor_novo, "liga o leitor por_cliente, que relê do offset 0")
    novo("lote", cmd_lote, "carrega o lote de pedidos do dia 3 na bronze")
    novo("validar", cmd_validar, "valida os pedidos pelo contrato e isola a quarentena")
    novo("regras", cmd_regras, "regra como código: falha o pipeline se a governança estiver incompleta")
    novo("catalogo", cmd_catalogo, "gera governanca/catalogo.md")
    novo("varredor", cmd_varredor, "procura dado pessoal escondido na bronze")
    novo("silver", cmd_silver, "constrói a camada silver", (["--com-data"], {"action": "store_true"}))
    novo("gold", cmd_gold, "constrói a visão de consumo", (["--k"], {"type": int, "default": 2}))
    novo("proteger", cmd_proteger, "crypto-shredding: cifra o cadastro da bronze com chave por titular (já ligado no `tudo`)")
    novo("esquecer", cmd_esquecer, "direito de ser esquecido", (["id"], {"type": int}))
    novo("reconstruir", cmd_reconstruir, "recria silver e gold a partir da bronze")
    novo("backup", cmd_backup, "cópia de segurança da bronze", (["--nome"], {"default": "dia1"}))
    novo("ensaio", cmd_ensaio, "ensaio do desastre, cronometrado", (["--nome"], {"default": "dia1"}))
    novo("tudo", cmd_tudo, "roda o pipeline do zero")
    novo("verificar", cmd_verificar, "roda tudo e confere cada número esperado")
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
