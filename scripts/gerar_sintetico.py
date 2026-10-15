#!/usr/bin/env python3
"""Gera dados/sintetico/: a mesma forma do dia 1 e nenhuma pessoa real (Missão 6, extra).
Determinístico (semente fixa). Nomes, e-mails, CPFs, telefones e IPs são todos inventados:
domínio .invalid, CPF com zeros e IPs da faixa de documentação 198.51.100.0/24."""
import csv
import pathlib
import random

DESTINO = pathlib.Path(__file__).resolve().parent.parent / "dados" / "sintetico"
CIDADES = ["Cidade A", "Cidade B", "Cidade C"]
STATUS = ["pago", "pago", "pendente", "cancelado"]
PAGINAS = ["/produto/a", "/produto/b", "/carrinho", "/home"]


def main():
    r = random.Random(2026)
    DESTINO.mkdir(parents=True, exist_ok=True)
    with open(DESTINO / "clientes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "nome", "email", "cpf", "nascimento", "cidade", "atualizado_em"])
        for i in range(1, 7):
            w.writerow([i, f"Pessoa Sintética {i:03d}", f"pessoa{i:03d}@sintetico.invalid", f"000.000.{i:03d}-00",
                        f"{r.randint(1975, 2002)}-{r.randint(1, 12):02d}-{r.randint(1, 28):02d}", r.choice(CIDADES),
                        f"2026-10-01T09:{i:02d}:00"])
    with open(DESTINO / "pedidos.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "cliente_id", "valor_centavos", "status", "criado_em", "atualizado_em", "observacao"])
        for i in range(1, 9):
            obs = "ligar para (00) 00000-0000" if i == 3 else ""
            w.writerow([100 + i, r.randint(1, 6), r.randint(1000, 30000), r.choice(STATUS),
                        f"2026-10-01T1{i % 10}:00:00", f"2026-10-01T1{i % 10}:05:00", obs])
    with open(DESTINO / "navegacao.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["evento_id", "cliente_id", "ip", "pagina", "quando"])
        for i in range(1, 9):
            w.writerow([i, "" if i == 6 else r.randint(1, 6), f"198.51.100.{i}", r.choice(PAGINAS),
                        f"2026-10-01T09:{50 + i:02d}:00"])
    print("gerado em", DESTINO)


if __name__ == "__main__":
    main()
