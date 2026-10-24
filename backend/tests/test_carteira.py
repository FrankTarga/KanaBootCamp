"""Modo carteira (POST /portfolio/validate e CLI): regras isoladas em estoques pequenos."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app import validar_carteira as cli
from app.main import app

from .conftest import (
    OUTRO_FUNDO,
    config_com,
    SACADO_BAIXADO,
    SACADO_CONCENTRADO,
    SACADO_GRANDE,
    SACADO_LIVRE,
    SACADO_MESMA_RAIZ,
    linha_csv,
    montar_csv,
)


def julgar(engine, *linhas, config=None):
    return engine.validar_carteira(montar_csv(*linhas), config)


def test_prazo_e_vencimento_contam_da_aquisicao_de_cada_linha(engine):
    """Data-base do motor é 22/10/2026, mas cada nota vale pela própria DATA_AQUISICAO."""
    sem_concentracao = config_com(engine, "CONCENTRACAO_MAXIMA_SACADO", ativo=False)
    antiga, longa, vencida = julgar(
        engine,
        linha_csv(SACADO_GRANDE, "A1", "1000,00", "07/10/2026", aquisicao="27/04/2026"),  # 163 dias: ok
        linha_csv(SACADO_GRANDE, "A2", "1000,00", "30/12/2026", aquisicao="01/06/2026"),  # 212 dias
        linha_csv(SACADO_GRANDE, "A3", "1000,00", "01/05/2026", aquisicao="02/05/2026"),
        config=sem_concentracao,
    )
    assert antiga == {"linha": 2, "id": "A1", "status": "APROVADO"}
    assert longa["barrado_por"] == ["PRAZO_MAXIMO"]
    assert vencida["barrado_por"] == ["NAO_VENCIDA"]


def test_concentracao_estatica_por_fundo_e_pela_raiz(engine):
    """No ANTECIPE, a raiz 11222333 tem 2 filiais que somam 15% das notas elegíveis: as duas caem.
    No outro fundo o mesmo cliente é 50%... mas só lá; e cada fundo é medido sozinho."""
    linhas = [linha_csv(SACADO_GRANDE, f"G{i}", "1000,00", "20/11/2026") for i in range(17)]
    linhas += [
        linha_csv(SACADO_CONCENTRADO, "C1", "1500,00", "20/11/2026"),
        linha_csv(SACADO_MESMA_RAIZ, "C2", "1500,00", "20/11/2026"),
        linha_csv(SACADO_LIVRE, "O1", "1000,00", "20/11/2026", fundo=OUTRO_FUNDO),
    ]
    r = {item["id"]: item for item in julgar(engine, *linhas)}
    assert r["C1"]["barrado_por"] == r["C2"]["barrado_por"] == ["CONCENTRACAO_MAXIMA_SACADO"]
    assert r["G0"]["barrado_por"] == ["CONCENTRACAO_MAXIMA_SACADO"]  # 17k de 20k = 85%
    assert r["O1"]["barrado_por"] == ["CONCENTRACAO_MAXIMA_SACADO"]  # 100% do outro fundo


def test_concentracao_so_avalia_nota_sem_outro_erro_e_ela_nao_conta_no_total(engine):
    linhas = [linha_csv(SACADO_GRANDE, "CHQ", "90000,00", "20/11/2026", tipo="Cheque")]
    linhas += [linha_csv(doc, f"N{i}", "1000,00", "20/11/2026") for i, doc in enumerate(
        [SACADO_LIVRE, SACADO_CONCENTRADO, SACADO_BAIXADO] * 4)]
    r = {item["id"]: item for item in julgar(engine, *linhas)}
    assert r["CHQ"]["barrado_por"] == ["TIPO_RECEBIVEL"]  # sem concentração junto
    assert r["N2"]["barrado_por"] == ["SITUACAO_CADASTRAL_SACADO"]
    # elegíveis: 4 notas do LIVRE e 4 do CONCENTRADO (raízes diferentes) = 50% cada, o cheque não entra na conta
    assert r["N0"]["barrado_por"] == r["N1"]["barrado_por"] == ["CONCENTRACAO_MAXIMA_SACADO"]


def test_sem_radar_de_duplicidade_e_id_original(engine):
    linhas = [linha_csv(SACADO_GRANDE, "000777", "1500,00", "10/11/2026") for _ in range(2)]  # = título do estoque
    linhas += [linha_csv(doc, f"D{i}", "1000,00", "20/11/2026") for i, doc in enumerate([SACADO_LIVRE, SACADO_CONCENTRADO] * 10)]
    r = julgar(engine, *linhas)
    assert r[0]["id"] == "000777"  # mantém os zeros como no arquivo
    assert all("DUPLICIDADE" not in c and "FRAUDE" not in c for item in r for c in item.get("barrado_por", []))


def test_ordem_das_regras_segue_o_json(engine):
    [item] = julgar(engine, linha_csv(SACADO_BAIXADO, "X", "50,00", "15/09/2027", tipo="Cheque"))
    assert item["barrado_por"] == ["SITUACAO_CADASTRAL_SACADO", "TIPO_RECEBIVEL", "VALOR_MINIMO", "PRAZO_MAXIMO"]


def test_endpoint_carteira(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.delenv("RECEITA_API_URL", raising=False)
    conteudo = montar_csv(linha_csv(SACADO_GRANDE, "E1", "1000,00", "20/11/2026"))
    with TestClient(app) as c:
        r = c.post("/api/v1/portfolio/validate", files={"file": ("carteira.csv", conteudo, "text/csv")})
        vazio = c.post("/api/v1/portfolio/validate", files={"file": ("c.csv", b" ", "text/csv")})
    # nota única = 100% da carteira daquele fundo: a concentração barra, como no gabarito
    assert r.status_code == 200
    assert r.json() == [{"linha": 2, "id": "E1", "status": "BARRADO", "barrado_por": ["CONCENTRACAO_MAXIMA_SACADO"]}]
    assert vazio.status_code == 422


def test_cli_escreve_no_formato_do_gabarito(pasta_dados, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.delenv("RECEITA_API_URL", raising=False)
    entrada, saida = tmp_path / "carteira.csv", tmp_path / "saida.json"
    entrada.write_bytes(montar_csv(linha_csv(SACADO_GRANDE, "E1", "1000,00", "20/11/2026"),
                                   linha_csv(SACADO_GRANDE, "E2", "50,00", "20/11/2026")))
    assert cli.main([str(entrada), str(saida)]) == 0
    assert json.loads(saida.read_text(encoding="utf-8")) == [
        {"linha": 2, "id": "E1", "status": "BARRADO", "barrado_por": ["CONCENTRACAO_MAXIMA_SACADO"]},
        {"linha": 3, "id": "E2", "status": "BARRADO", "barrado_por": ["VALOR_MINIMO"]},
    ]
    assert "2 linhas, 2 barradas" in capsys.readouterr().err
    assert cli.main([]) == 2


# ---------------------------------------------------------------------------
# modo=carteira no POST /batches/validate (a tela usa a mesma rota do lote)
# ---------------------------------------------------------------------------

def _carteira_rica(engine, *linhas, **kwargs):
    return engine.validar_lote(montar_csv(*linhas), modo="carteira", **kwargs)


def test_modo_carteira_rico_tem_os_mesmos_status_do_formato_gabarito(engine):
    linhas = [linha_csv(SACADO_GRANDE, f"G{i}", "1000,00", "20/11/2026") for i in range(17)]
    linhas += [linha_csv(SACADO_CONCENTRADO, "C1", "1500,00", "20/11/2026"),
               linha_csv(SACADO_LIVRE, "L1", "50,00", "20/11/2026"),
               linha_csv(SACADO_BAIXADO, "B1", "1000,00", "20/11/2026")]
    gabarito = julgar(engine, *linhas)
    rico = _carteira_rica(engine, *linhas)
    assert [("APROVADO" if i.status == "APROVADA" else "BARRADO") for i in rico.itens] == [g["status"] for g in gabarito]
    assert [sorted(e.codigo for e in i.erros) for i in rico.itens] == [sorted(g.get("barrado_por", [])) for g in gabarito]
    assert all(e.mensagem_empresa and e.acao_recomendada for i in rico.itens for e in i.erros)
    assert rico.meta.otimizador_ativo is False and rico.meta.ganho_otimizador_reais == 0


def test_modo_carteira_explica_a_concentracao_com_os_totais_do_arquivo(engine):
    r = _carteira_rica(engine, linha_csv(SACADO_GRANDE, "U1", "1000,00", "20/11/2026"))
    msg = r.itens[0].erros[0].mensagem_empresa
    assert r.itens[0].erros[0].codigo == "CONCENTRACAO_MAXIMA_SACADO"
    assert "Nas notas aceitas deste arquivo para o ANTECIPE FIDC" in msg
    assert "soma R$ 1.000,00 de R$ 1.000,00, ou seja, 100,00% do total, acima do limite de 10,00% por cliente" in msg
    assert "Diversifique" in r.itens[0].erros[0].acao_recomendada


def test_modo_carteira_usa_a_aquisicao_da_linha_e_precifica(engine):
    sem_concentracao = config_com(engine, "CONCENTRACAO_MAXIMA_SACADO", ativo=False)
    [item] = _carteira_rica(engine, linha_csv(SACADO_GRANDE, "P1", "10000,00", "07/10/2026", aquisicao="27/04/2026"),
                            config=sem_concentracao).itens
    assert item.status == "APROVADA" and item.prazo_dias == 163 and item.data_aquisicao == "27/04/2026"
    assert item.desagio_reais == round(10000 * 0.02 * 163 / 30, 2)


def test_api_modo_carteira_sem_limite_de_linhas_do_lote(pasta_dados, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(pasta_dados))
    monkeypatch.setenv("MAX_LINHAS_LOTE", "2")
    monkeypatch.delenv("RECEITA_API_URL", raising=False)
    conteudo = montar_csv(*(linha_csv(SACADO_GRANDE, f"X{i}", "1000,00", "20/11/2026") for i in range(3)))
    with TestClient(app) as c:
        enviar = lambda **d: c.post("/api/v1/batches/validate", files={"file": ("l.csv", conteudo, "text/csv")}, data=d)  # noqa: E731
        assert enviar().json()["error"]["code"] == "ARQUIVO_INVALIDO"  # lote: limite de 2 notas
        carteira = enviar(modo="carteira")
        assert carteira.status_code == 200 and carteira.json()["resumo"]["total_notas"] == 3
        assert enviar(modo="xyz").json()["error"]["code"] == "MODO_INVALIDO"
