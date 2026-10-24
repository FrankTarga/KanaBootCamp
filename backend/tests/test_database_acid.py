"""Testes de conformidade ACID e Liquidação Idempotente (RFC-001).

Test-Driven Development (TDD):
Esta suíte define os comportamentos esperados da camada de persistência transacional
em SQLite com WAL, prevenção de dupla cessão, rollback atômico, integridade referencial,
trilha de auditoria e sincronização Write-Through com o StockIndex O(1).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.stock_index import StockIndex, gerar_hash_titulo


# ---------------------------------------------------------------------------
# Fixtures e Utilitários de Teste
# ---------------------------------------------------------------------------

@pytest.fixture
def db_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Garante que os testes rodem em um banco SQLite isolado e temporário."""
    import app.database as db_mod

    caminho_db = tmp_path / "antecipe_acid_teste.db"
    monkeypatch.setattr(db_mod, "DB_PATH", caminho_db)
    db_mod.init_db()
    return caminho_db


def criar_item_nota(
    nu_documento: str,
    status: str = "APROVADA",
    valor_nominal: float = 1000.0,
    desagio_reais: float = 20.0,
    doc_cedente: str = "76123456000199",
    nome_cedente: str = "CEDENTE TESTE LTDA",
    doc_sacado: str = "11222333000188",
    nome_sacado: str = "SACADO TESTE S.A.",
    vencimento: str = "25/11/2026",
    tipo: str = "Duplicata",
) -> dict:
    hash_titulo = gerar_hash_titulo(doc_cedente, doc_sacado, nu_documento, valor_nominal, vencimento)
    return {
        "linha_csv": 2,
        "ordem_avaliacao": 1,
        "hash_titulo": hash_titulo,
        "nu_documento": nu_documento,
        "nome_cedente": nome_cedente,
        "doc_cedente": doc_cedente,
        "nome_sacado": nome_sacado,
        "doc_sacado": doc_sacado,
        "tipo_recebivel": tipo,
        "valor_nominal": valor_nominal,
        "data_vencimento": vencimento,
        "data_aquisicao": "22/10/2026",
        "prazo_dias": 34,
        "desagio_reais": desagio_reais,
        "valor_liquido": valor_nominal - desagio_reais,
        "status": status,
        "severidade": "OK" if status == "APROVADA" else "REGRA_NEGOCIO",
        "salva_pelo_otimizador": False,
        "erros": [] if status == "APROVADA" else [{"codigo": "VALOR_MINIMO", "titulo_amigavel": "Valor abaixo do mínimo"}],
    }


def criar_payload_validacao(
    batch_hash: str = "batch_hash_teste_001",
    qtd_aprovadas: int = 2,
    qtd_recusadas: int = 1,
    doc_cedente: str = "76123456000199",
) -> dict:
    itens = []
    for i in range(1, qtd_aprovadas + 1):
        itens.append(criar_item_nota(f"NF-{i:03d}", status="APROVADA", doc_cedente=doc_cedente))
    for j in range(1, qtd_recusadas + 1):
        itens.append(criar_item_nota(f"REC-{j:03d}", status="RECUSADA", doc_cedente=doc_cedente))

    total = qtd_aprovadas + qtd_recusadas
    bruto_total = sum(i["valor_nominal"] for i in itens)
    liquido_aprovado = sum(i["valor_liquido"] for i in itens if i["status"] == "APROVADA")

    return {
        "meta": {
            "batch_hash_idempotencia": batch_hash,
            "tempo_processamento_ms": 12.5,
            "data_base_utilizada": "22/10/2026",
            "taxa_mensal_aplicada": 0.02,
            "otimizador_ativo": True,
            "valor_liquido_sem_otimizador": liquido_aprovado,
            "ganho_otimizador_reais": 0.0,
            "qtd_notas_salvas_otimizador": 0,
        },
        "resumo": {
            "total_notas": total,
            "qtd_aprovadas": qtd_aprovadas,
            "qtd_recusadas": qtd_recusadas,
            "qtd_alertas_fraude": 0,
            "valor_bruto_total": bruto_total,
            "valor_bruto_aprovado": sum(i["valor_nominal"] for i in itens if i["status"] == "APROVADA"),
            "valor_bruto_recusado": sum(i["valor_nominal"] for i in itens if i["status"] == "RECUSADA"),
            "desagio_total": sum(i["desagio_reais"] for i in itens if i["status"] == "APROVADA"),
            "valor_liquido_receber": liquido_aprovado,
            "prazo_medio_ponderado_dias": 34.0,
            "contagem_por_motivo": [],
        },
        "itens": itens,
        "analise_recusas": {
            "qtd_notas": total,
            "qtd_recusadas": qtd_recusadas,
            "pct_recusadas": round(qtd_recusadas / total * 100, 1) if total else 0.0,
            "valor_recusado": sum(i["valor_nominal"] for i in itens if i["status"] == "RECUSADA"),
            "qtd_com_mais_de_um_erro": 0,
            "pct_com_mais_de_um_erro": 0.0,
            "grupos": {"um_problema": [], "mais_de_um_problema": {"qtd": 0, "valor": 0.0, "pct_das_recusadas": 0.0, "subgrupos": []}},
            "motivos": [],
        },
    }


# ===========================================================================
# 1. Testes de Configuração de Engenharia ACID e PRAGMAs
# ===========================================================================

def test_pragmas_acid_e_concorrencia_wal(db_temp: Path):
    """Verifica se os PRAGMAs bancários (WAL, FULL synchronous, foreign_keys) estão ativos."""
    import app.database as db_mod

    with db_mod.get_acid_connection(write_lock=False) as conn:
        journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert journal_mode.lower() == "wal", f"Esperado journal_mode=WAL, obtido {journal_mode}"

        synchronous = conn.execute("PRAGMA synchronous;").fetchone()[0]
        # 2 = FULL, 3 = EXTRA
        assert synchronous in (2, "FULL", 3, "EXTRA"), f"Esperado synchronous=FULL, obtido {synchronous}"

        fk = conn.execute("PRAGMA foreign_keys;").fetchone()[0]
        assert fk == 1, "PRAGMA foreign_keys deve ser 1 (ON)"

        timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
        assert timeout == 5000, f"Esperado busy_timeout=5000, obtido {timeout}"


def test_transacao_commit_e_rollback_automatico(db_temp: Path):
    """Verifica se o contextmanager faz COMMIT em caso de sucesso e ROLLBACK em exceção."""
    import app.database as db_mod

    # Sucesso: deve persistir
    with db_mod.get_acid_connection(write_lock=True) as conn:
        conn.execute(
            "INSERT INTO auditoria_regras (criado_em, usuario_email, acao, regras_ativas_count, json_anterior, json_novo) "
            "VALUES ('2026-10-24 18:00:00', 'admin@antecipe.com.br', 'TESTE_COMMIT', 7, '{}', '{}')"
        )

    with db_mod.get_acid_connection(write_lock=False) as conn:
        linhas = conn.execute("SELECT COUNT(*) FROM auditoria_regras WHERE acao = 'TESTE_COMMIT'").fetchone()[0]
        assert linhas == 1

    # Exceção: deve abortar (ROLLBACK) e não gravar
    with pytest.raises(RuntimeError):
        with db_mod.get_acid_connection(write_lock=True) as conn:
            conn.execute(
                "INSERT INTO auditoria_regras (criado_em, usuario_email, acao, regras_ativas_count, json_anterior, json_novo) "
                "VALUES ('2026-10-24 18:00:00', 'admin@antecipe.com.br', 'TESTE_ROLLBACK', 7, '{}', '{}')"
            )
            raise RuntimeError("Erro forçado para disparar ROLLBACK")

    with db_mod.get_acid_connection(write_lock=False) as conn:
        linhas_rb = conn.execute("SELECT COUNT(*) FROM auditoria_regras WHERE acao = 'TESTE_ROLLBACK'").fetchone()[0]
        assert linhas_rb == 0, "Transação abortada não deve persistir registros no banco!"


# ===========================================================================
# 2. Testes de DDL, Tabelas, Índices e CHECK Constraints
# ===========================================================================

def test_schema_tabelas_e_indices_criados(db_temp: Path):
    """Garante que as 3 tabelas e os índices B-Tree foram criados."""
    with sqlite3.connect(str(db_temp)) as conn:
        cursor = conn.cursor()
        tabelas = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "lotes_operacoes" in tabelas
        assert "titulos_adquiridos" in tabelas
        assert "auditoria_regras" in tabelas

        indices = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
        assert "idx_titulos_sacado" in indices
        assert "idx_titulos_cedente" in indices


def test_check_constraints_rejeitam_valores_invalidos(db_temp: Path):
    """Verifica se CHECK constraints rejeitam valores negativos ou status inválidos."""
    import app.database as db_mod

    # Status de lote inválido
    with pytest.raises(sqlite3.IntegrityError):
        with db_mod.get_acid_connection(write_lock=True) as conn:
            conn.execute("""
                INSERT INTO lotes_operacoes (
                    batch_hash, criado_em, cedente_nome, cedente_doc, data_base_utilizada,
                    taxa_mensal, total_notas, qtd_aprovadas, qtd_recusadas, valor_bruto_total,
                    valor_liquido_aprovado, status_operacao, payload_resposta_json
                ) VALUES ('b1', '2026-10-24', 'Cedente', '123', '22/10/2026', 0.02, 1, 1, 0, 100, 98, 'STATUS_INEXISTENTE', '{}')
            """)

    # Valor nominal <= 0 em titulos_adquiridos
    payload = criar_payload_validacao("b_check", qtd_aprovadas=1, qtd_recusadas=0)
    db_mod.salvar_simulacao_lote(payload)

    with pytest.raises(sqlite3.IntegrityError):
        with db_mod.get_acid_connection(write_lock=True) as conn:
            conn.execute("""
                INSERT INTO titulos_adquiridos (
                    hash_titulo, batch_hash, nome_fundo, doc_cedente, nome_cedente,
                    doc_sacado, nome_sacado, nu_documento, tipo_recebivel,
                    valor_nominal, desagio_reais, valor_liquido, data_vencimento, data_aquisicao, adquirido_em
                ) VALUES ('h1', 'b_check', 'ANTECIPE FIDC', 'ced', 'Cedente', 'sac', 'Sacado', '1', 'Dup', -50.0, 0, -50.0, '25/11/2026', '22/10/2026', '2026-10-24')
            """)


def test_foreign_key_restricao_batch_inexistente(db_temp: Path):
    """Verifica que título adquirido não pode referenciar batch_hash inexistente."""
    import app.database as db_mod

    with pytest.raises(sqlite3.IntegrityError):
        with db_mod.get_acid_connection(write_lock=True) as conn:
            conn.execute("""
                INSERT INTO titulos_adquiridos (
                    hash_titulo, batch_hash, nome_fundo, doc_cedente, nome_cedente,
                    doc_sacado, nome_sacado, nu_documento, tipo_recebivel,
                    valor_nominal, desagio_reais, valor_liquido, data_vencimento, data_aquisicao, adquirido_em
                ) VALUES ('h_orfao', 'batch_que_nao_existe', 'ANTECIPE FIDC', 'c', 'C', 's', 'S', '1', 'D', 100, 2, 98, '25/11/2026', '22/10/2026', '2026-10-24')
            """)


# ===========================================================================
# 3. Testes de Simulação de Lote (salvar_simulacao_lote)
# ===========================================================================

def test_salvar_simulacao_lote_novo_e_atualizacao(db_temp: Path):
    """Garante a inserção correta de um lote simulado e o comportamento do ON CONFLICT."""
    import app.database as db_mod

    payload = criar_payload_validacao("batch_simulacao_01", qtd_aprovadas=2, qtd_recusadas=1)
    res = db_mod.salvar_simulacao_lote(payload)
    assert res["batch_hash"] == "batch_simulacao_01"
    assert res["status_operacao"] == "SIMULADO"

    # Confere no banco
    with db_mod.get_acid_connection(write_lock=False) as conn:
        row = conn.execute("SELECT * FROM lotes_operacoes WHERE batch_hash = 'batch_simulacao_01'").fetchone()
        assert row is not None
        assert row["status_operacao"] == "SIMULADO"
        assert row["total_notas"] == 3
        assert row["qtd_aprovadas"] == 2
        assert row["qtd_recusadas"] == 1


def test_salvar_simulacao_preserva_status_liquidado(db_temp: Path):
    """Se o lote já foi LIQUIDADO, salvar nova simulação não pode reverter o status para SIMULADO."""
    import app.database as db_mod

    payload = criar_payload_validacao("batch_liq_01", qtd_aprovadas=2, qtd_recusadas=0)
    db_mod.salvar_simulacao_lote(payload)
    db_mod.liquidar_lote_acid("batch_liq_01")

    # Re-simula o mesmo lote
    res = db_mod.salvar_simulacao_lote(payload)
    assert res["status_operacao"] == "LIQUIDADO"

    with db_mod.get_acid_connection(write_lock=False) as conn:
        row = conn.execute("SELECT status_operacao, liquidado_em FROM lotes_operacoes WHERE batch_hash = 'batch_liq_01'").fetchone()
        assert row["status_operacao"] == "LIQUIDADO"
        assert row["liquidado_em"] is not None


# ===========================================================================
# 4. Testes de Liquidação Financeira ACID e Idempotência
# ===========================================================================

def test_liquidar_lote_acid_sucesso(db_temp: Path):
    """Liquidação compra todas as notas aprovadas e atualiza status do lote de forma atômica."""
    import app.database as db_mod

    payload = criar_payload_validacao("batch_sucesso_01", qtd_aprovadas=3, qtd_recusadas=1)
    db_mod.salvar_simulacao_lote(payload)

    resultado = db_mod.liquidar_lote_acid("batch_sucesso_01")
    assert resultado["status"] == "LIQUIDADO"
    assert resultado["qtd_titulos_comprados"] == 3
    assert len(resultado["titulos_comprados"]) == 3

    with db_mod.get_acid_connection(write_lock=False) as conn:
        lote = conn.execute("SELECT status_operacao, liquidado_em FROM lotes_operacoes WHERE batch_hash = 'batch_sucesso_01'").fetchone()
        assert lote["status_operacao"] == "LIQUIDADO"
        assert lote["liquidado_em"] is not None

        titulos = conn.execute("SELECT * FROM titulos_adquiridos WHERE batch_hash = 'batch_sucesso_01'").fetchall()
        assert len(titulos) == 3
        # Confere se todas pertencem ao ANTECIPE FIDC
        assert all(t["nome_fundo"] == "ANTECIPE FIDC" for t in titulos)


def test_liquidar_lote_idempotente_ja_liquidado(db_temp: Path):
    """Chamar liquidação para um lote já liquidado retorna JA_LIQUIDADO sem duplicar títulos."""
    import app.database as db_mod

    payload = criar_payload_validacao("batch_idem_01", qtd_aprovadas=2, qtd_recusadas=0)
    db_mod.salvar_simulacao_lote(payload)
    primeira = db_mod.liquidar_lote_acid("batch_idem_01")
    assert primeira["status"] == "LIQUIDADO"

    # Segunda chamada (Idempotência)
    segunda = db_mod.liquidar_lote_acid("batch_idem_01")
    assert segunda["status"] == "JA_LIQUIDADO"
    assert "anteriormente" in segunda["mensagem"]

    # Garante que não duplicou os títulos
    with db_mod.get_acid_connection(write_lock=False) as conn:
        total = conn.execute("SELECT COUNT(*) FROM titulos_adquiridos WHERE batch_hash = 'batch_idem_01'").fetchone()[0]
        assert total == 2


def test_liquidar_lote_inexistente_lanca_key_error(db_temp: Path):
    """Tentar liquidar um batch_hash não encontrado lança KeyError."""
    import app.database as db_mod

    with pytest.raises(KeyError) as exc_info:
        db_mod.liquidar_lote_acid("hash_que_nao_existe")
    assert "não encontrado" in str(exc_info.value)


def test_liquidar_lote_sem_aprovadas_lanca_value_error(db_temp: Path):
    """Lote com 0 notas aprovadas não pode ser liquidado."""
    import app.database as db_mod

    payload = criar_payload_validacao("batch_so_recusas", qtd_aprovadas=0, qtd_recusadas=3)
    db_mod.salvar_simulacao_lote(payload)

    with pytest.raises(ValueError) as exc_info:
        db_mod.liquidar_lote_acid("batch_so_recusas")
    assert "não possui notas aprovadas" in str(exc_info.value)


# ===========================================================================
# 5. Teste Crítico: Dupla Cessão Concorrente & ACID Rollback Atômico
# ===========================================================================

def test_dupla_cessao_concorrente_dispara_acid_rollback(db_temp: Path):
    """
    CENÁRIO CRÍTICO DE ENGENHARIA BANCÁRIA:
    Lote A tem [Nota 1, Nota 2].
    Lote B tem [Nota 2, Nota 3].
    1. Liquida Lote A -> Sucesso. Nota 1 e 2 compradas.
    2. Tenta liquidar Lote B -> Conflito na Nota 2 (UNIQUE constraint em hash_titulo).
    3. O banco DEVE abortar a transação inteira do Lote B (ROLLBACK).
    4. Nota 3 NÃO PODE ficar inserida (Atomicidade 'tudo ou nada').
    5. Lote B DEVE permanecer como 'SIMULADO', não 'LIQUIDADO'.
    """
    import app.database as db_mod

    # Criando os itens
    nota1 = criar_item_nota("NF-001", status="APROVADA", valor_nominal=1000.0)
    nota2 = criar_item_nota("NF-002", status="APROVADA", valor_nominal=2000.0)
    nota3 = criar_item_nota("NF-003", status="APROVADA", valor_nominal=3000.0)

    # Lote A: Nota 1 e Nota 2
    payload_a = criar_payload_validacao("LOTE_A", qtd_aprovadas=2, qtd_recusadas=0)
    payload_a["itens"] = [nota1, nota2]

    # Lote B: Nota 2 (colisão!) e Nota 3
    payload_b = criar_payload_validacao("LOTE_B", qtd_aprovadas=2, qtd_recusadas=0)
    payload_b["itens"] = [nota2, nota3]

    db_mod.salvar_simulacao_lote(payload_a)
    db_mod.salvar_simulacao_lote(payload_b)

    # 1. Liquidação do Lote A -> OK
    res_a = db_mod.liquidar_lote_acid("LOTE_A")
    assert res_a["status"] == "LIQUIDADO"

    # 2. Liquidação do Lote B -> DEVE FALHAR por violação de unicidade da Nota 2
    with pytest.raises(ValueError) as exc_info:
        db_mod.liquidar_lote_acid("LOTE_B")

    msg = str(exc_info.value)
    assert "ACID Rollback" in msg or "já foram adquiridos" in msg

    # 3. VERIFICAÇÃO DE ATOMICIDADE STRICT NO BANCO
    with db_mod.get_acid_connection(write_lock=False) as conn:
        # Nota 3 NÃO PODE ter sido inserida
        nota3_gravada = conn.execute(
            "SELECT * FROM titulos_adquiridos WHERE hash_titulo = ?", (nota3["hash_titulo"],)
        ).fetchone()
        assert nota3_gravada is None, "ATENÇÃO: Violação de atomicidade! Nota 3 foi inserida apesar do rollback!"

        # Lote B NÃO PODE constar como liquidado
        lote_b = conn.execute(
            "SELECT status_operacao, liquidado_em FROM lotes_operacoes WHERE batch_hash = 'LOTE_B'"
        ).fetchone()
        assert lote_b["status_operacao"] == "SIMULADO"
        assert lote_b["liquidado_em"] is None


# ===========================================================================
# 6. Testes de Leitura e Trilha de Auditoria
# ===========================================================================

def test_carregar_titulos_liquidados_db(db_temp: Path):
    """Verifica carregamento de títulos do SQLite para reconstrução de memória no Startup."""
    import app.database as db_mod

    payload = criar_payload_validacao("batch_carga_01", qtd_aprovadas=2, qtd_recusadas=0)
    db_mod.salvar_simulacao_lote(payload)
    db_mod.liquidar_lote_acid("batch_carga_01")

    titulos = db_mod.carregar_titulos_liquidados_db()
    assert len(titulos) == 2
    assert "hash_titulo" in titulos[0]
    assert "doc_sacado" in titulos[0]
    assert "valor_nominal" in titulos[0]


def test_trilha_auditoria_regras(db_temp: Path):
    """Verifica registro imutável e listagem ordenada da auditoria de regras."""
    import app.database as db_mod

    db_mod.registrar_auditoria_validadores(
        usuario_email="gestor@antecipe.com.br",
        acao="ALTERAR_TAXA",
        regras_ativas_count=7,
        json_anterior={"taxa": 0.02},
        json_novo={"taxa": 0.025},
    )

    db_mod.registrar_auditoria_validadores(
        usuario_email="banca@antecipe.com.br",
        acao="DESATIVAR_VALOR_MINIMO",
        regras_ativas_count=6,
        json_anterior={"ativo": True},
        json_novo={"ativo": False},
    )

    logs = db_mod.listar_auditoria_validadores(limite=10)
    assert len(logs) == 2
    # Ordenado por id DESC (mais recente primeiro)
    assert logs[0]["acao"] == "DESATIVAR_VALOR_MINIMO"
    assert logs[1]["acao"] == "ALTERAR_TAXA"
    assert logs[0]["usuario_email"] == "banca@antecipe.com.br"


def test_listar_historico_operacoes(db_temp: Path):
    """Verifica listagem de histórico para o front-end."""
    import app.database as db_mod

    p1 = criar_payload_validacao("batch_hist_01", qtd_aprovadas=1, qtd_recusadas=0)
    p2 = criar_payload_validacao("batch_hist_02", qtd_aprovadas=2, qtd_recusadas=1)
    db_mod.salvar_simulacao_lote(p1)
    db_mod.salvar_simulacao_lote(p2)

    hist = db_mod.listar_historico_operacoes(limite=10)
    assert len(hist) == 2
    hashes = [h["batch_hash"] for h in hist]
    assert "batch_hist_01" in hashes
    assert "batch_hist_02" in hashes


# ===========================================================================
# 7. Teste de Sincronização Write-Through com StockIndex
# ===========================================================================

def test_sincronizacao_write_through_stock_index():
    """
    Garante que o método auxiliar registrar_novo_titulo_antecipe do StockIndex:
    1. Adiciona o hash_titulo ao conjunto de títulos do ANTECIPE;
    2. Incrementa o patrimônio do fundo;
    3. Atualiza a exposição por sacado (completa e raiz) e cedente.
    """
    stock_index = StockIndex(nome_fundo="ANTECIPE FIDC")
    assert stock_index.patrimonio_antecipe == 0.0

    doc_cedente = "76123456000199"
    doc_sacado = "11222333000188"
    hash_t1 = "hash_teste_sync_001"
    valor = 15000.0

    # Chamada do método Write-Through especificado na RFC
    assert hasattr(stock_index, "registrar_novo_titulo_antecipe"), \
        "StockIndex deve implementar o método registrar_novo_titulo_antecipe conforme a RFC-001"

    stock_index.registrar_novo_titulo_antecipe(
        hash_titulo=hash_t1,
        doc_sacado=doc_sacado,
        doc_cedente=doc_cedente,
        valor_nominal=valor,
    )

    # 1. Verificação no set de hashes do ANTECIPE
    assert hash_t1 in stock_index.hashes_antecipe
    # 2. Verificação do patrimônio
    assert stock_index.patrimonio_antecipe == 15000.0
    # 3. Verificação de exposição
    assert stock_index.exposicao_sacado[doc_sacado] == 15000.0
    assert stock_index.exposicao_sacado_raiz[doc_sacado[:8]] == 15000.0
    assert stock_index.exposicao_cedente[doc_cedente] == 15000.0
    assert stock_index.exposicao_cedente_raiz[doc_cedente[:8]] == 15000.0


# ===========================================================================
# 8. Testes de Integração das Rotas REST da RFC (/liquidate, /history, /audit)
# ===========================================================================

def test_rotas_api_liquidate_history_e_audit(db_temp: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Testa as rotas especificadas no passo 6 da RFC:
    - POST /api/v1/batches/{batch_hash}/liquidate (200 sucesso, 404 ausente, 409 conflito)
    - GET /api/v1/batches/history
    - GET /api/v1/validators/audit
    """
    from app.main import app

    with TestClient(app) as client:
        # 1. Tentar liquidar lote inexistente -> 404
        r404 = client.post("/api/v1/batches/hash_fantasma/liquidate")
        assert r404.status_code == 404

        # 2. Simula e liquida com sucesso
        import app.database as db_mod
        payload = criar_payload_validacao("batch_api_test", qtd_aprovadas=2, qtd_recusadas=0)
        db_mod.salvar_simulacao_lote(payload)

        r_liq = client.post("/api/v1/batches/batch_api_test/liquidate")
        assert r_liq.status_code == 200
        dados_liq = r_liq.json()
        assert dados_liq["status"] == "LIQUIDADO"
        assert dados_liq["qtd_titulos_comprados"] == 2

        # 3. Histórico de lotes
        r_hist = client.get("/api/v1/batches/history")
        assert r_hist.status_code == 200
        assert "historico" in r_hist.json()
        assert any(item["batch_hash"] == "batch_api_test" for item in r_hist.json()["historico"])

        # 4. Trilha de auditoria de regras
        db_mod.registrar_auditoria_validadores(
            "admin@antecipe.com.br", "TESTE_API", 7, {}, {}
        )
        r_audit = client.get("/api/v1/validators/audit")
        assert r_audit.status_code == 200
        assert "auditoria" in r_audit.json()
        assert any(item["acao"] == "TESTE_API" for item in r_audit.json()["auditoria"])


# ===========================================================================
# 9. Testes de Usuários e Autenticação ACID (Login)
# ===========================================================================

def test_salvar_e_autenticar_usuario(db_temp: Path):
    """Garante cadastro, hash scrypt com salt, atualização e login de usuários no SQLite ACID."""
    import app.database as db_mod

    # 1. Salvar gestor e cedente
    db_mod.salvar_usuario("gestor@antecipe.com.br", "SenhaSegura123", "Gestor do Fundo", "Gestor", "GESTOR")
    db_mod.salvar_usuario("empresa@antecipe.com.br", "SenhaEmpresa456", "Empresa Cedente LTDA", "Cedente", "CEDENTE")

    # 2. Autenticação bem-sucedida
    u_gestor = db_mod.autenticar_usuario("gestor@antecipe.com.br", "SenhaSegura123")
    assert u_gestor is not None
    assert u_gestor["email"] == "gestor@antecipe.com.br"
    assert u_gestor["role"] == "GESTOR"
    assert "senha_hash" not in u_gestor  # Nunca vazar hash de senha

    u_cedente = db_mod.autenticar_usuario("empresa@antecipe.com.br", "SenhaEmpresa456")
    assert u_cedente is not None
    assert u_cedente["role"] == "CEDENTE"

    # 3. Credenciais inválidas
    assert db_mod.autenticar_usuario("gestor@antecipe.com.br", "senha_errada") is None
    assert db_mod.autenticar_usuario("inexistente@antecipe.com.br", "qualquer") is None

    # 4. Case-insensitive no e-mail
    u_case = db_mod.autenticar_usuario("  GESTOR@ANTECIPE.COM.BR ", "SenhaSegura123")
    assert u_case is not None
    assert u_case["email"] == "gestor@antecipe.com.br"

    # 5. Atualização de senha/dados via upsert
    db_mod.salvar_usuario("gestor@antecipe.com.br", "NovaSenha789", "Novo Nome", "Diretor", "GESTOR")
    assert db_mod.autenticar_usuario("gestor@antecipe.com.br", "SenhaSegura123") is None
    u_atualizado = db_mod.autenticar_usuario("gestor@antecipe.com.br", "NovaSenha789")
    assert u_atualizado is not None
    assert u_atualizado["nome"] == "Novo Nome"
    assert u_atualizado["cargo"] == "Diretor"


def test_usuario_role_check_constraint(db_temp: Path):
    """Verifica que a constraint CHECK restringe papéis estritamente a GESTOR ou CEDENTE."""
    import app.database as db_mod

    with pytest.raises(sqlite3.IntegrityError):
        with db_mod.get_acid_connection(write_lock=True) as conn:
            conn.execute("""
                INSERT INTO usuarios (email, senha_hash, nome, cargo, role, criado_em)
                VALUES ('hacker@antecipe.com.br', 'hash', 'Hacker', 'Cargo', 'ROLE_INVALIDA', '2026-10-24')
            """)


# ===========================================================================
# 10. Testes de Suporte a Documentos Comprobatórios e PDFs de Notas Fiscais
# ===========================================================================

def test_schema_documentos_notas_fiscais_e_migracoes(db_temp: Path):
    """Garante que a tabela de documentos comprobatórios e os campos de rastreabilidade existem."""
    with sqlite3.connect(str(db_temp)) as conn:
        cursor = conn.cursor()
        tabelas = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "documentos_notas_fiscais" in tabelas

        indices = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
        assert "idx_doc_batch" in indices
        assert "idx_doc_chave" in indices
        assert "idx_doc_hash" in indices

        colunas_lotes = [r[1] for r in cursor.execute("PRAGMA table_info(lotes_operacoes)").fetchall()]
        assert "origem_lote" in colunas_lotes
        assert "qtd_documentos_pdf" in colunas_lotes

        colunas_titulos = [r[1] for r in cursor.execute("PRAGMA table_info(titulos_adquiridos)").fetchall()]
        assert "chave_acesso" in colunas_titulos
        assert "documento_id" in colunas_titulos


def test_check_constraints_documentos_notas_fiscais(db_temp: Path):
    """Garante que restrições CHECK rejeitam valores espúrios na tabela de documentos."""
    import app.database as db_mod

    # Cria lote base
    payload = criar_payload_validacao("b_docs_check", qtd_aprovadas=1, qtd_recusadas=0)
    db_mod.salvar_simulacao_lote(payload)

    # 1. tamanho_bytes <= 0
    with pytest.raises(sqlite3.IntegrityError):
        with db_mod.get_acid_connection(write_lock=True) as conn:
            conn.execute("""
                INSERT INTO documentos_notas_fiscais (
                    batch_hash, hash_arquivo_sha256, nome_arquivo_original, tamanho_bytes,
                    tipo_documento, metodo_extracao, confianca_extracao, dados_extraidos_json,
                    status_processamento, criado_em
                ) VALUES ('b_docs_check', 'hash1', 'nf.pdf', 0, 'NFE', 'HEURISTICA_SEFAZ', 1.0, '{}', 'PROCESSADO', '2026-10-24')
            """)

    # 2. tipo_documento inválido
    with pytest.raises(sqlite3.IntegrityError):
        with db_mod.get_acid_connection(write_lock=True) as conn:
            conn.execute("""
                INSERT INTO documentos_notas_fiscais (
                    batch_hash, hash_arquivo_sha256, nome_arquivo_original, tamanho_bytes,
                    tipo_documento, metodo_extracao, confianca_extracao, dados_extraidos_json,
                    status_processamento, criado_em
                ) VALUES ('b_docs_check', 'hash2', 'nf.pdf', 1024, 'FORMATO_INVALIDO', 'HEURISTICA_SEFAZ', 1.0, '{}', 'PROCESSADO', '2026-10-24')
            """)

    # 3. confianca_extracao fora do intervalo [0.0, 1.0]
    with pytest.raises(sqlite3.IntegrityError):
        with db_mod.get_acid_connection(write_lock=True) as conn:
            conn.execute("""
                INSERT INTO documentos_notas_fiscais (
                    batch_hash, hash_arquivo_sha256, nome_arquivo_original, tamanho_bytes,
                    tipo_documento, metodo_extracao, confianca_extracao, dados_extraidos_json,
                    status_processamento, criado_em
                ) VALUES ('b_docs_check', 'hash3', 'nf.pdf', 1024, 'NFE', 'HEURISTICA_SEFAZ', 1.5, '{}', 'PROCESSADO', '2026-10-24')
            """)


def test_salvar_e_listar_documentos_nota_fiscal(db_temp: Path):
    """Testa o ciclo de vida completo de gravação e consulta de PDFs processados."""
    import app.database as db_mod

    batch_hash = "batch_pdf_teste_001"
    payload = criar_payload_validacao(batch_hash, qtd_aprovadas=2, qtd_recusadas=0)
    db_mod.salvar_simulacao_lote(payload, origem_lote="PDF_LOTE", qtd_documentos_pdf=2)

    # 1. Salva 1 DANFE NF-e lida via Heurística SEFAZ
    chave_nfe = "35261012345678000195550010000010451000010458"
    doc_id_1 = db_mod.salvar_documento_nota_fiscal(
        batch_hash=batch_hash,
        hash_arquivo_sha256="sha256_pdf_nfe_danfe_001",
        nome_arquivo_original="danfe_nf_1045.pdf",
        tamanho_bytes=245800,
        tipo_documento="NFE",
        metodo_extracao="HEURISTICA_SEFAZ",
        dados_extraidos_json={"nu_documento": "1045", "valor": 1000.0, "vencimento": "25/11/2026"},
        chave_acesso=chave_nfe,
        confianca_extracao=1.0,
    )
    assert doc_id_1 > 0

    # 2. Salva 1 NFS-e lida via Fallback Multimodal (Vision)
    doc_id_2 = db_mod.salvar_documento_nota_fiscal(
        batch_hash=batch_hash,
        hash_arquivo_sha256="sha256_pdf_nfse_sp_002",
        nome_arquivo_original="nfse_prefeitura_sp.pdf",
        tamanho_bytes=189400,
        tipo_documento="NFSE",
        metodo_extracao="MULTIMODAL_VISION",
        dados_extraidos_json={"nu_documento": "8821", "valor": 1000.0, "cidade": "São Paulo"},
        chave_acesso=None,
        confianca_extracao=0.98,
    )
    assert doc_id_2 > doc_id_1

    # 3. Lista documentos por lote
    docs = db_mod.listar_documentos_lote(batch_hash)
    assert len(docs) == 2
    assert docs[0]["nome_arquivo_original"] == "danfe_nf_1045.pdf"
    assert docs[0]["tipo_documento"] == "NFE"
    assert docs[0]["chave_acesso"] == chave_nfe
    assert docs[0]["dados_extraidos_json"]["nu_documento"] == "1045"
    assert docs[1]["metodo_extracao"] == "MULTIMODAL_VISION"

    # 4. Busca por hash de arquivo (antifraude de reenvio de PDF)
    doc_por_hash = db_mod.obter_documento_por_hash_arquivo("sha256_pdf_nfe_danfe_001")
    assert doc_por_hash is not None
    assert doc_por_hash["id"] == doc_id_1

    assert db_mod.obter_documento_por_hash_arquivo("hash_fantasma") is None

    # 5. Busca por chave de acesso
    doc_por_chave = db_mod.obter_documento_por_chave_acesso(chave_nfe)
    assert doc_por_chave is not None
    assert doc_por_chave["id"] == doc_id_1


def test_liquidacao_com_chave_acesso_e_documento_vinculado(db_temp: Path):
    """Garante que a liquidação armazena chave de acesso e documento_id no título adquirido."""
    import app.database as db_mod

    batch_hash = "batch_liq_com_pdf"
    chave_acesso = "35261076123456000199550010000007771000007774"
    payload = criar_payload_validacao(batch_hash, qtd_aprovadas=1, qtd_recusadas=0)

    # Anexa chave_acesso no item aprovado
    payload["itens"][0]["chave_acesso"] = chave_acesso
    db_mod.salvar_simulacao_lote(payload, origem_lote="PDF_LOTE", qtd_documentos_pdf=1)

    doc_id = db_mod.salvar_documento_nota_fiscal(
        batch_hash=batch_hash,
        hash_arquivo_sha256="sha256_pdf_liq_doc",
        nome_arquivo_original="nf_000777.pdf",
        tamanho_bytes=102400,
        tipo_documento="NFE",
        metodo_extracao="HEURISTICA_SEFAZ",
        dados_extraidos_json={"nu_documento": "000777"},
        chave_acesso=chave_acesso,
    )
    payload["itens"][0]["documento_id"] = doc_id

    # Atualiza o snapshot com o documento_id
    db_mod.salvar_simulacao_lote(payload)

    # Liquida
    res_liq = db_mod.liquidar_lote_acid(batch_hash)
    assert res_liq["status"] == "LIQUIDADO"

    with db_mod.get_acid_connection(write_lock=False) as conn:
        linha = conn.execute(
            "SELECT chave_acesso, documento_id FROM titulos_adquiridos WHERE batch_hash = ?",
            (batch_hash,)
        ).fetchone()
        assert linha is not None
        assert linha["chave_acesso"] == chave_acesso
        assert linha["documento_id"] == doc_id


def test_foreign_key_documento_com_batch_inexistente(db_temp: Path):
    """Garante que não é possível anexar documento a um lote inexistente (FK RESTRICT/CASCADE)."""
    import app.database as db_mod

    with pytest.raises(sqlite3.IntegrityError):
        db_mod.salvar_documento_nota_fiscal(
            batch_hash="lote_fantasma_999",
            hash_arquivo_sha256="sha256_invalido",
            nome_arquivo_original="invalido.pdf",
            tamanho_bytes=5000,
            tipo_documento="NFE",
            metodo_extracao="HEURISTICA_SEFAZ",
            dados_extraidos_json={},
        )


