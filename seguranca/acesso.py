"""Dois papéis (Missão 6): o PIPELINE lê a camada bronze e escreve nas demais; o ANALISTA lê só a silver e a gold,
e só para leitura. Aqui a regra é imposta no código (e o analista abre o banco em modo somente leitura).
Em produção, o mesmo desenho vira usuários e permissões do banco ou do sistema de arquivos
(ver seguranca/matriz.md)."""
import json

import comum

PERMISSOES = {
    "pipeline": {"origem": "leitura", "bronze": "escrita", "silver": "escrita", "gold": "escrita"},
    "analista": {"silver": "leitura", "gold": "leitura"},
}


def _auditar(papel, camada, resultado):
    """Trilha de leitura (classes confidencial e pessoal): quem abriu o quê, e se foi negado."""
    with open(comum.estado() / "auditoria.log", "a", encoding="utf-8") as f:
        f.write(json.dumps({"quando": comum.agora(), "papel": papel, "camada": camada, "resultado": resultado}) + "\n")


def abrir(papel, camada):
    nivel = PERMISSOES.get(papel, {}).get(camada)
    if nivel is None:
        _auditar(papel, camada, "negado")
        raise PermissionError(f"o papel '{papel}' não pode ler a camada '{camada}'")
    _auditar(papel, camada, nivel)
    return comum.conectar(camada, somente_leitura=(nivel == "leitura"))
