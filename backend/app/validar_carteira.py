"""CLI do modo carteira: python -m app.validar_carteira <estoque.csv> [saida.json]

Usa backend/data (validadores e situação cadastral) e as mesmas envs da API (RECEITA_API_URL etc.).
Sem saida.json, escreve o JSON no stdout.
"""

import json
import sys
from pathlib import Path

from .main import carregar_settings
from .rule_engine import CadastroSituacao, RuleEngine, carregar_config
from .stock_index import carregar_estoque


def main(argv: list[str]) -> int:
    if not 1 <= len(argv) <= 2:
        print(__doc__, file=sys.stderr)
        return 2
    settings = carregar_settings()
    config = carregar_config(settings.validadores_path)
    index = carregar_estoque(settings.estoque_path, config.fundo.nome, config.fundo.cnpj, settings.data_base_padrao)
    cadastro = CadastroSituacao(settings.cadastro_path, settings.receita_api_url, settings.receita_timeout_s)
    engine = RuleEngine(index, config, settings.validadores_path, cadastro)
    resultado = engine.validar_carteira(Path(argv[0]).read_bytes())
    texto = "[\n" + ",\n".join(json.dumps(item, ensure_ascii=False) for item in resultado) + "\n]\n"
    if len(argv) == 2:
        Path(argv[1]).write_text(texto, encoding="utf-8")
    else:
        sys.stdout.write(texto)
    barrados = sum(1 for item in resultado if item["status"] == "BARRADO")
    print(f"{len(resultado)} linhas, {barrados} barradas", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
