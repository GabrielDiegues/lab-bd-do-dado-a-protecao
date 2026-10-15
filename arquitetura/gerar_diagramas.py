#!/usr/bin/env python3
"""Fonte do desenho (Missão 10). Gera estrutura.svg e vida-do-dado.svg.

  estrutura.svg      origem, cargas, camadas, quarentena, consumo, chave e cópias.
                     Lote (traço cheio) e captura de mudanças/fluxo (tracejado) têm traços diferentes;
                     cada caixa traz a classe da camada e quem acessa.
  vida-do-dado.svg   a vida de um dado pessoal (a cliente 5), do cadastro à eliminação, morada por morada.

Para mudar o desenho, edite este arquivo e rode:  python3 arquitetura/gerar_diagramas.py"""
import html
import pathlib

AQUI = pathlib.Path(__file__).resolve().parent

CORES = {  # classe -> (faixa, fundo)
    "pessoal": ("#b3261e", "#fdf1f0"),
    "pessoal cifrado": ("#b45309", "#fff7ed"),
    "pseudonimizado": ("#6d28d9", "#f5f3ff"),
    "agregado": ("#047857", "#ecfdf5"),
    "interno": ("#475569", "#f1f5f9"),
    "doc": ("#94a3b8", "#ffffff"),
}
TRACOS = {
    "lote": 'stroke="#1e293b" stroke-width="2.4"',
    "fluxo": 'stroke="#0369a1" stroke-width="2" stroke-dasharray="9 5"',
    "desvio": 'stroke="#b3261e" stroke-width="2" stroke-dasharray="2 5"',
    "regra": 'stroke="#94a3b8" stroke-width="1.4"',
    "copia": 'stroke="#047857" stroke-width="2" stroke-dasharray="14 4 2 4"',
}


def esc(t):
    return html.escape(t, quote=False)


class Desenho:
    def __init__(self, w, h, titulo):
        self.w, self.h, self.titulo = w, h, titulo
        self.partes = []

    def caixa(self, x, y, w, h, linhas, classe="interno", forte=True):
        faixa, fundo = CORES[classe]
        self.partes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fundo}" stroke="{faixa}" stroke-width="1.6"/>')
        if forte:
            self.partes.append(f'<rect x="{x}" y="{y}" width="6" height="{h}" rx="3" fill="{faixa}"/>')
        ty = y + 20
        for i, l in enumerate(linhas):
            estilo = 'font-weight="700" font-size="14"' if i == 0 else 'font-size="11.5" fill="#334155"'
            self.partes.append(f'<text x="{x + 16}" y="{ty}" {estilo}>{esc(l)}</text>')
            ty += 18 if i == 0 else 15

    def seta(self, pontos, tipo, rotulo=None, rx=None, ry=None):
        d = "M" + " L".join(f"{x},{y}" for x, y in pontos)
        self.partes.append(f'<path d="{d}" fill="none" {TRACOS[tipo]} marker-end="url(#seta-{tipo})"/>')
        if rotulo:
            x, y = (rx, ry) if rx is not None else pontos[0]
            self.partes.append(f'<text x="{x}" y="{y}" font-size="11" fill="#475569" font-style="italic">{esc(rotulo)}</text>')

    def texto(self, x, y, t, tamanho=12, peso="400", cor="#334155", ancora="start"):
        self.partes.append(f'<text x="{x}" y="{y}" font-size="{tamanho}" font-weight="{peso}" fill="{cor}" text-anchor="{ancora}">{esc(t)}</text>')

    def svg(self):
        marcadores = "".join(
            f'<marker id="seta-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
            f'<path d="M0,0 L10,5 L0,10 z" fill="{"#1e293b" if k == "lote" else "#0369a1" if k == "fluxo" else "#b3261e" if k == "desvio" else "#047857" if k == "copia" else "#94a3b8"}"/></marker>'
            for k in TRACOS)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                f'font-family="Helvetica, Arial, sans-serif"><title>{esc(self.titulo)}</title>'
                f'<defs>{marcadores}</defs><rect width="100%" height="100%" fill="#ffffff"/>' + "".join(self.partes) + "</svg>\n")


def estrutura():
    d = Desenho(1380, 740, "Loja online · estrutura do pipeline (do dado à proteção)")
    d.texto(30, 32, "Do dado à proteção · visão de estrutura", 20, "700", "#0f172a")
    d.texto(30, 52, "Cifra em trânsito e em repouso em todas as setas e camadas (o piso universal). Quem acessa: pipeline = lê e escreve · analista = só lê silver e gold.", 11.5)

    # documentos (governança)
    d.caixa(30, 84, 210, 56, ["lista de eliminação", "esquecer: vale em toda morada"], "doc", forte=False)
    d.caixa(480, 84, 180, 56, ["acordo de governança", "dono · classe · retenção"], "doc", forte=False)
    d.caixa(730, 84, 170, 56, ["contratos", "campos · regras · classe"], "doc", forte=False)
    d.caixa(940, 84, 190, 56, ["CHAVE_PSEUDONIMO", "ambiente · fora do código"], "doc", forte=False)
    d.caixa(250, 150, 220, 58, ["cofre de chaves por titular", "AES-GCM · apagar = esquecer"], "doc", forte=False)

    # linha principal
    d.caixa(30, 240, 215, 100, ["Origem", "banco da loja · classe: pessoal", "clientes · pedidos · navegacao", "acesso: aplicação da loja"], "pessoal")
    d.caixa(480, 240, 170, 110, ["Bronze", "cópia fiel · classe: pessoal", "cadastro cifrado por titular", "acesso: só o pipeline"], "pessoal cifrado")
    d.caixa(730, 240, 140, 100, ["Validação", "aplica o contrato", "linha a linha"], "interno")
    d.caixa(940, 240, 200, 110, ["Silver", "validada · protegida", "pseudônimo HMAC · sem CPF/IP", "acesso: analista (leitura)"], "pseudonimizado")
    d.caixa(1190, 240, 170, 110, ["Gold", "receita_por_cidade", "agregado · K ≥ 2", "acesso: analista (leitura)"], "agregado")
    d.caixa(730, 410, 140, 70, ["Quarentena", "linha + motivo", "classe: pessoal"], "pessoal")

    # fluxo de mudanças e de eventos
    d.caixa(250, 400, 190, 70, ["Log de mudanças (CDC)", "gatilhos · só anexa · offset", "classe: pessoal · retenção curta"], "pessoal")
    d.caixa(250, 520, 190, 70, ["Tópico navegacao", "só anexa · guarda por tempo", "lápide + compactação (LGPD)"], "pessoal")
    d.caixa(480, 520, 190, 70, ["Leitores (offset próprio)", "visitas · por_cliente · bronze", "idempotentes · pelo menos uma vez"], "interno")

    # cópias
    d.caixa(940, 420, 170, 70, ["Cópia de segurança", "bronze + offsets + manifesto", "outra pasta · SHA-256"], "interno")
    d.caixa(1180, 420, 170, 70, ["Cópia isolada", "imutável · credencial", "independente · 3-2-1-1-0"], "interno")
    d.caixa(1180, 530, 190, 56, ["cópia da chave", "fora do ambiente da produção"], "doc", forte=False)

    # setas
    d.seta([(245, 290), (480, 290)], "lote", "carga incremental · marca-d'água", 258, 280)
    d.seta([(130, 340), (130, 435), (250, 435)], "fluxo", "captura de mudanças", 138, 400)
    d.seta([(440, 435), (540, 435), (540, 350)], "fluxo", "em ordem", 548, 405)
    d.seta([(70, 340), (70, 555), (250, 555)], "fluxo", "cliques", 78, 540)
    d.seta([(440, 555), (480, 555)], "fluxo")
    d.seta([(600, 520), (600, 350)], "fluxo")
    d.seta([(650, 290), (730, 290)], "lote")
    d.seta([(870, 290), (940, 290)], "lote")
    d.seta([(1140, 290), (1190, 290)], "lote")
    d.seta([(800, 340), (800, 410)], "desvio", "reprovada", 808, 380)
    d.seta([(660, 112), (730, 112)], "regra")
    d.seta([(800, 140), (800, 240)], "regra", "contrato", 808, 190)
    d.seta([(1040, 140), (1040, 240)], "regra", "pseudônimo", 1048, 190)
    d.seta([(470, 179), (500, 179), (500, 240)], "regra")
    d.seta([(135, 140), (135, 240)], "regra", "elimina", 143, 190)
    d.seta([(630, 350), (630, 505), (1025, 505), (1025, 490)], "copia", "cópia diária", 700, 498)
    d.seta([(1110, 455), (1180, 455)], "copia")
    d.seta([(1265, 490), (1265, 530)], "copia")

    # legenda
    y = 650
    d.texto(30, y, "Legenda", 12, "700")
    itens = [("lote", "carga em lote (traço cheio)"), ("fluxo", "captura de mudanças e fluxo de eventos (tracejado)"),
             ("desvio", "desvio: o que não passou (pontilhado)"), ("regra", "contrato, regra e chave (fino)"), ("copia", "cópia de segurança")]
    x = 30
    for k, t in itens:
        d.partes.append(f'<path d="M{x},{y + 20} L{x + 46},{y + 20}" fill="none" {TRACOS[k]}/>')
        d.texto(x + 54, y + 24, t, 11)
        x += 54 + len(t) * 6 + 24
    x = 30
    for k in ("pessoal", "pessoal cifrado", "pseudonimizado", "agregado", "interno"):
        faixa, fundo = CORES[k]
        d.partes.append(f'<rect x="{x}" y="{y + 44}" width="16" height="16" rx="3" fill="{fundo}" stroke="{faixa}" stroke-width="1.6"/>')
        d.texto(x + 22, y + 57, "classe: " + k, 11)
        x += 150
    return d.svg()


def vida_do_dado():
    colunas = ["Dia 1 · cadastro", "Dia 2 · exclusão no CDC", "Missão 8 · esquecer 5", "Missão 9 · restauração"]
    # cada célula: (texto, cor)
    R, L, V, C, I = "pessoal", "pessoal cifrado", "agregado", "pseudonimizado", "interno"
    linhas = [
        ("Origem · cadastro", [("nome, e-mail, CPF, nascimento, cidade (real)", R), ("DELETE: sai da origem", V), ("ausente", V), ("ausente", V)]),
        ("Origem · recado do pedido 106", [("telefone no texto livre (real)", R), ("telefone (real)", R), ("campo limpo; o pedido fica", V), ("campo limpo", V)]),
        ("Origem · navegação", [("2 eventos com o IP (real)", R), ("2 eventos (real)", R), ("eventos apagados", V), ("sem os eventos", V)]),
        ("Log de mudanças", [("captura desligada ainda", I), ("exclusão registrada só com a chave", I), ("carga útil zerada", V), ("reaplicado: nada dela", V)]),
        ("Tópico navegacao", [("eventos com IP (real)", R), ("eventos com IP (real)", R), ("lápide + compactação", V), ("lápide relida", V)]),
        ("Estado dos leitores", [("contagens por página e por cliente", I), ("contagens", I), ("eventos dela removidos", V), ("reconstruído do log", V)]),
        ("Bronze", [("cadastro cifrado (chave dela)", L), ("DELETE propagado; resto real", R), ("tudo tratado; chave apagada", V), ("cópia traz tudo; lista reaplicada", V)]),
        ("Silver e gold", [("pseudônimo (HMAC)", C), ("pseudônimo; pedido 106 sem cadastro", C), ("reconstruída; cliente_ps vazio", V), ("reconstruída da bronze", V)]),
        ("Cópia de segurança do dia 1", [("cadastro cifrado + IP/telefone reais", L), ("idem (cópia é fotografia)", L), ("expira; sem a chave, o cadastro é ruído", V), ("restaurada → lista de eliminação reaplicada", V)]),
    ]
    larg_rot, larg_col, alt = 220, 270, 56
    w = 30 + larg_rot + 4 * larg_col + 30
    h = 110 + len(linhas) * (alt + 8) + 110
    d = Desenho(w, h, "A vida de um dado pessoal · cliente 5")
    d.texto(30, 32, "Do dado à proteção · visão de fluxo: a vida de um dado pessoal (cliente 5)", 20, "700", "#0f172a")
    d.texto(30, 52, "Do cadastro à eliminação, morada por morada. Cor = forma do dado naquela morada, naquele momento.", 11.5)
    x0, y0 = 30 + larg_rot, 76
    for i, c in enumerate(colunas):
        d.texto(x0 + i * larg_col + larg_col / 2, y0 + 16, c, 13, "700", "#0f172a", "middle")
    for r, (rot, cels) in enumerate(linhas):
        y = y0 + 30 + r * (alt + 8)
        d.texto(30, y + alt / 2 + 4, rot, 12.5, "700", "#0f172a")
        for i, (t, cor) in enumerate(cels):
            faixa, fundo = CORES[cor]
            x = x0 + i * larg_col + 4
            d.partes.append(f'<rect x="{x}" y="{y}" width="{larg_col - 12}" height="{alt}" rx="6" fill="{fundo}" stroke="{faixa}" stroke-width="1.5"/>')
            palavras, linha, linhas_t = t.split(), "", []
            for p in palavras:
                if len(linha) + len(p) + 1 > 38:
                    linhas_t.append(linha)
                    linha = p
                else:
                    linha = (linha + " " + p).strip()
            linhas_t.append(linha)
            for k, lt in enumerate(linhas_t[:3]):
                d.texto(x + 10, y + 20 + k * 15, lt, 11.5)
    y = y0 + 30 + len(linhas) * (alt + 8) + 18
    itens = [(R, "dado real"), (L, "cifrado com a chave do titular"), (C, "pseudônimo"), (I, "sem dado pessoal ou só metadado"), (V, "ausente / eliminado")]
    x = 30
    for k, t in itens:
        faixa, fundo = CORES[k]
        d.partes.append(f'<rect x="{x}" y="{y}" width="16" height="16" rx="3" fill="{fundo}" stroke="{faixa}" stroke-width="1.6"/>')
        d.texto(x + 22, y + 13, t, 11.5)
        x += 30 + len(t) * 7 + 20
    d.texto(30, y + 44, "Pedido 106: continua (nota fiscal, LGPD art. 16, I), sem pessoa. A receita não muda. Pseudônimo não é anônimo: por isso a silver não tem CPF, nome, e-mail, IP nem observação.", 11.5)
    return d.svg()


if __name__ == "__main__":
    (AQUI / "estrutura.svg").write_text(estrutura(), encoding="utf-8")
    (AQUI / "vida-do-dado.svg").write_text(vida_do_dado(), encoding="utf-8")
    print("gerados:", AQUI / "estrutura.svg", AQUI / "vida-do-dado.svg")
