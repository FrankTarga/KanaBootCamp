"""Camada de Persistência Transacional ACID e Liquidação Idempotente (RFC-001).

Padrão Arquitetural: Híbrido Write-Through (Leitura O(1) In-Memory + Escrita Transacional ACID em SQLite com WAL).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH: Path | None = None


def get_db_path() -> Path:
    if DB_PATH is not None:
        return Path(DB_PATH)
    data_dir = Path(os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR)))
    return data_dir / "antecipe_acid.db"


@contextmanager
def get_acid_connection(write_lock: bool = False):
    """Gerenciador de conexão SQLite configurado para conformidade ACID estrita.

    Se write_lock=True, inicia transação 'BEGIN IMMEDIATE' para isolamento serializável.
    """
    caminho = get_db_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(caminho), timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        # Configurações PRAGMA para ACID, Concorrência WAL e Integridade Referencial
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = FULL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")

        if write_lock:
            conn.execute("BEGIN IMMEDIATE;")
        else:
            conn.execute("BEGIN;")

        yield conn
        if conn.in_transaction:
            conn.execute("COMMIT;")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK;")
        raise
    finally:
        conn.close()


def _migrar_schema(conn: sqlite3.Connection) -> None:
    """Aplica migrações incrementais preservando integridade e dados existentes."""
    colunas_lotes = {row["name"] for row in conn.execute("PRAGMA table_info(lotes_operacoes)").fetchall()}
    if "origem_lote" not in colunas_lotes:
        conn.execute("ALTER TABLE lotes_operacoes ADD COLUMN origem_lote TEXT NOT NULL DEFAULT 'CSV';")
    if "qtd_documentos_pdf" not in colunas_lotes:
        conn.execute("ALTER TABLE lotes_operacoes ADD COLUMN qtd_documentos_pdf INTEGER NOT NULL DEFAULT 0;")

    colunas_titulos = {row["name"] for row in conn.execute("PRAGMA table_info(titulos_adquiridos)").fetchall()}
    if "chave_acesso" not in colunas_titulos:
        conn.execute("ALTER TABLE titulos_adquiridos ADD COLUMN chave_acesso TEXT;")
    if "documento_id" not in colunas_titulos:
        conn.execute("ALTER TABLE titulos_adquiridos ADD COLUMN documento_id INTEGER REFERENCES documentos_notas_fiscais(id);")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_titulos_chave ON titulos_adquiridos(chave_acesso);")


def init_db():
    """Inicializa o schema relacional ACID e os índices B-Tree."""
    with get_acid_connection(write_lock=True) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS lotes_operacoes (
                batch_hash TEXT PRIMARY KEY,
                criado_em TEXT NOT NULL,
                liquidado_em TEXT,
                cedente_nome TEXT NOT NULL,
                cedente_doc TEXT NOT NULL,
                data_base_utilizada TEXT NOT NULL,
                taxa_mensal REAL NOT NULL CHECK (taxa_mensal >= 0),
                total_notas INTEGER NOT NULL CHECK (total_notas >= 0),
                qtd_aprovadas INTEGER NOT NULL CHECK (qtd_aprovadas >= 0),
                qtd_recusadas INTEGER NOT NULL CHECK (qtd_recusadas >= 0),
                valor_bruto_total REAL NOT NULL CHECK (valor_bruto_total >= 0),
                valor_liquido_aprovado REAL NOT NULL CHECK (valor_liquido_aprovado >= 0),
                ganho_otimizador REAL NOT NULL DEFAULT 0.0,
                status_operacao TEXT NOT NULL CHECK (status_operacao IN ('SIMULADO', 'LIQUIDADO', 'CANCELADO')),
                origem_lote TEXT NOT NULL DEFAULT 'CSV' CHECK (origem_lote IN ('CSV', 'PDF_LOTE', 'API')),
                qtd_documentos_pdf INTEGER NOT NULL DEFAULT 0 CHECK (qtd_documentos_pdf >= 0),
                payload_resposta_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documentos_notas_fiscais (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_hash             TEXT    NOT NULL,
                hash_arquivo_sha256    TEXT    NOT NULL,
                nome_arquivo_original  TEXT    NOT NULL,
                tamanho_bytes          INTEGER NOT NULL CHECK (tamanho_bytes > 0),
                mime_type              TEXT    NOT NULL DEFAULT 'application/pdf',
                tipo_documento         TEXT    NOT NULL CHECK (tipo_documento IN ('NFE', 'NFSE', 'CTE', 'OUTRO')),
                chave_acesso           TEXT,
                metodo_extracao        TEXT    NOT NULL CHECK (metodo_extracao IN ('HEURISTICA_SEFAZ', 'MULTIMODAL_VISION', 'MANUAL', 'CSV')),
                confianca_extracao     REAL    NOT NULL DEFAULT 1.0 CHECK (confianca_extracao >= 0.0 AND confianca_extracao <= 1.0),
                dados_extraidos_json   TEXT    NOT NULL,
                status_processamento   TEXT    NOT NULL DEFAULT 'PROCESSADO' CHECK (status_processamento IN ('PENDENTE', 'PROCESSADO', 'FALHA_LEITURA')),
                erro_mensagem          TEXT,
                criado_em              TEXT    NOT NULL,
                FOREIGN KEY (batch_hash) REFERENCES lotes_operacoes(batch_hash) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_doc_batch ON documentos_notas_fiscais(batch_hash);
            CREATE INDEX IF NOT EXISTS idx_doc_chave ON documentos_notas_fiscais(chave_acesso);
            CREATE INDEX IF NOT EXISTS idx_doc_hash ON documentos_notas_fiscais(hash_arquivo_sha256);

            CREATE TABLE IF NOT EXISTS titulos_adquiridos (
                hash_titulo TEXT PRIMARY KEY,
                batch_hash TEXT NOT NULL,
                nome_fundo TEXT NOT NULL DEFAULT 'ANTECIPE FIDC',
                doc_cedente TEXT NOT NULL,
                nome_cedente TEXT NOT NULL,
                doc_sacado TEXT NOT NULL,
                nome_sacado TEXT NOT NULL,
                nu_documento TEXT NOT NULL,
                tipo_recebivel TEXT NOT NULL,
                valor_nominal REAL NOT NULL CHECK (valor_nominal > 0),
                desagio_reais REAL NOT NULL CHECK (desagio_reais >= 0),
                valor_liquido REAL NOT NULL CHECK (valor_liquido >= 0),
                data_vencimento TEXT NOT NULL,
                data_aquisicao TEXT NOT NULL,
                adquirido_em TEXT NOT NULL,
                chave_acesso TEXT,
                documento_id INTEGER,
                FOREIGN KEY (batch_hash) REFERENCES lotes_operacoes(batch_hash) ON DELETE RESTRICT,
                FOREIGN KEY (documento_id) REFERENCES documentos_notas_fiscais(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_titulos_sacado ON titulos_adquiridos(doc_sacado);
            CREATE INDEX IF NOT EXISTS idx_titulos_cedente ON titulos_adquiridos(doc_cedente);

            CREATE TABLE IF NOT EXISTS auditoria_regras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                criado_em TEXT NOT NULL,
                usuario_email TEXT NOT NULL,
                acao TEXT NOT NULL,
                regras_ativas_count INTEGER NOT NULL,
                json_anterior TEXT NOT NULL,
                json_novo TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS usuarios (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT    NOT NULL UNIQUE,
                senha_hash TEXT    NOT NULL,
                nome       TEXT    NOT NULL,
                cargo      TEXT    NOT NULL,
                role       TEXT    NOT NULL CHECK (role IN ('CEDENTE', 'GESTOR')),
                criado_em  TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
        """)
        _migrar_schema(conn)


def salvar_simulacao_lote(
    payload_validacao: dict[str, Any],
    origem_lote: str = "CSV",
    qtd_documentos_pdf: int = 0
) -> dict[str, Any]:
    """Salva ou atualiza uma simulação de lote de forma atômica.

    Se o lote já tiver sido LIQUIDADO anteriormente, preserva o registro imutável.
    """
    meta = payload_validacao.get("meta", {})
    resumo = payload_validacao.get("resumo", {})
    itens = payload_validacao.get("itens", [])

    batch_hash = meta.get("batch_hash_idempotencia")
    if not batch_hash:
        batch_hash = hashlib.sha256(
            json.dumps(itens, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:32]

    primeiro_item = itens[0] if itens else {}
    cedente_nome = primeiro_item.get("nome_cedente", "Empresa Cedente")
    cedente_doc = primeiro_item.get("doc_cedente", "00000000000000")
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_acid_connection(write_lock=True) as conn:
        existente = conn.execute(
            "SELECT status_operacao, liquidado_em FROM lotes_operacoes WHERE batch_hash = ?",
            (batch_hash,)
        ).fetchone()

        # Trava de Imutabilidade ACID: Lote já LIQUIDADO não pode ter seu snapshot alterado
        if existente and existente["status_operacao"] == "LIQUIDADO":
            return {
                "batch_hash": batch_hash,
                "status_operacao": "LIQUIDADO",
                "liquidado_em": existente["liquidado_em"]
            }

        conn.execute("""
            INSERT INTO lotes_operacoes (
                batch_hash, criado_em, liquidado_em, cedente_nome, cedente_doc,
                data_base_utilizada, taxa_mensal, total_notas, qtd_aprovadas,
                qtd_recusadas, valor_bruto_total, valor_liquido_aprovado,
                ganho_otimizador, status_operacao, origem_lote, qtd_documentos_pdf,
                payload_resposta_json
            ) VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SIMULADO', ?, ?, ?)
            ON CONFLICT(batch_hash) DO UPDATE SET
                criado_em = excluded.criado_em,
                data_base_utilizada = excluded.data_base_utilizada,
                taxa_mensal = excluded.taxa_mensal,
                total_notas = excluded.total_notas,
                qtd_aprovadas = excluded.qtd_aprovadas,
                qtd_recusadas = excluded.qtd_recusadas,
                valor_bruto_total = excluded.valor_bruto_total,
                valor_liquido_aprovado = excluded.valor_liquido_aprovado,
                ganho_otimizador = excluded.ganho_otimizador,
                origem_lote = excluded.origem_lote,
                qtd_documentos_pdf = excluded.qtd_documentos_pdf,
                payload_resposta_json = excluded.payload_resposta_json
            WHERE lotes_operacoes.status_operacao != 'LIQUIDADO'
        """, (
            batch_hash,
            agora,
            cedente_nome,
            cedente_doc,
            meta.get("data_base_utilizada", "22/10/2026"),
            float(meta.get("taxa_mensal_aplicada", 0.025)),
            int(resumo.get("total_notas", 0)),
            int(resumo.get("qtd_aprovadas", 0)),
            int(resumo.get("qtd_recusadas", 0)),
            float(resumo.get("valor_bruto_total", 0.0)),
            float(resumo.get("valor_liquido_receber", 0.0)),
            float(meta.get("ganho_otimizador_reais", 0.0)),
            origem_lote.strip().upper(),
            int(qtd_documentos_pdf),
            json.dumps(payload_validacao, ensure_ascii=False)
        ))

    return {"batch_hash": batch_hash, "status_operacao": "SIMULADO"}


def liquidar_lote_acid(batch_hash: str) -> dict[str, Any]:
    """Transação ACID de Liquidação Financeira (Compra efetiva dos recebíveis).

    Garante que nenhuma nota aprovada no lote tenha sido comprada em paralelo.
    Se houver colisão de hash_titulo, faz ROLLBACK completo e levanta ValueError.
    """
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_acid_connection(write_lock=True) as conn:
        lote = conn.execute(
            "SELECT status_operacao, payload_resposta_json, data_base_utilizada FROM lotes_operacoes WHERE batch_hash = ?",
            (batch_hash,)
        ).fetchone()

        if not lote:
            raise KeyError(f"Lote {batch_hash} não encontrado no banco de dados.")

        if lote["status_operacao"] == "LIQUIDADO":
            return {
                "batch_hash": batch_hash,
                "status": "JA_LIQUIDADO",
                "mensagem": "Este lote já foi liquidado anteriormente (Operação Idempotente)."
            }

        payload = json.loads(lote["payload_resposta_json"])
        itens_aprovados = [i for i in payload.get("itens", []) if i.get("status") == "APROVADA"]

        if not itens_aprovados:
            raise ValueError("O lote não possui notas aprovadas elegíveis para liquidação.")

        titulos_inseridos = []
        try:
            for item in itens_aprovados:
                # Fallback seguro caso hash_titulo não esteja explícito no item
                hash_titulo = item.get("hash_titulo") or hashlib.sha256(
                    f"{item.get('doc_cedente')}|{item.get('doc_sacado')}|{item.get('nu_documento')}|{item.get('valor_nominal')}|{item.get('data_vencimento')}".encode("utf-8")
                ).hexdigest()

                conn.execute("""
                    INSERT INTO titulos_adquiridos (
                        hash_titulo, batch_hash, nome_fundo, doc_cedente, nome_cedente,
                        doc_sacado, nome_sacado, nu_documento, tipo_recebivel,
                        valor_nominal, desagio_reais, valor_liquido,
                        data_vencimento, data_aquisicao, adquirido_em,
                        chave_acesso, documento_id
                    ) VALUES (?, ?, 'ANTECIPE FIDC', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    hash_titulo,
                    batch_hash,
                    str(item.get("doc_cedente", "")),
                    str(item.get("nome_cedente", "")),
                    str(item.get("doc_sacado", "")),
                    str(item.get("nome_sacado", "")),
                    str(item.get("nu_documento", "")),
                    str(item.get("tipo_recebivel", "Duplicata")),
                    float(item.get("valor_nominal", 0.0)),
                    float(item.get("desagio_reais", 0.0)),
                    float(item.get("valor_liquido", 0.0)),
                    str(item.get("data_vencimento", "")),
                    lote["data_base_utilizada"],
                    agora,
                    item.get("chave_acesso"),
                    item.get("documento_id")
                ))
                item["hash_titulo"] = hash_titulo
                titulos_inseridos.append(item)
        except sqlite3.IntegrityError as exc:
            # Dispara ROLLBACK automático pelo contextmanager!
            raise ValueError(
                f"Transação abortada (ACID Rollback): Um ou mais títulos deste lote já foram "
                f"adquiridos em outra operação concorrente. Detalhe técnico: {exc}"
            ) from exc

        conn.execute("""
            UPDATE lotes_operacoes
            SET status_operacao = 'LIQUIDADO', liquidado_em = ?
            WHERE batch_hash = ?
        """, (agora, batch_hash))

    return {
        "batch_hash": batch_hash,
        "status": "LIQUIDADO",
        "liquidado_em": agora,
        "qtd_titulos_comprados": len(titulos_inseridos),
        "titulos_comprados": titulos_inseridos
    }


# ---------------------------------------------------------------------------
# Gestão de Documentos Comprobatórios e PDFs de Notas Fiscais
# ---------------------------------------------------------------------------

def salvar_documento_nota_fiscal(
    batch_hash: str,
    hash_arquivo_sha256: str,
    nome_arquivo_original: str,
    tamanho_bytes: int,
    tipo_documento: str,
    metodo_extracao: str,
    dados_extraidos_json: dict[str, Any] | list[Any],
    chave_acesso: str | None = None,
    confianca_extracao: float = 1.0,
    status_processamento: str = "PROCESSADO",
    erro_mensagem: str | None = None,
) -> int:
    """Registra documento comprobatório (PDF) de nota fiscal vinculado ao lote."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_acid_connection(write_lock=True) as conn:
        cursor = conn.execute("""
            INSERT INTO documentos_notas_fiscais (
                batch_hash, hash_arquivo_sha256, nome_arquivo_original, tamanho_bytes,
                mime_type, tipo_documento, chave_acesso, metodo_extracao,
                confianca_extracao, dados_extraidos_json, status_processamento,
                erro_mensagem, criado_em
            ) VALUES (?, ?, ?, ?, 'application/pdf', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            batch_hash,
            hash_arquivo_sha256,
            nome_arquivo_original,
            tamanho_bytes,
            tipo_documento.strip().upper(),
            chave_acesso.strip() if chave_acesso else None,
            metodo_extracao.strip().upper(),
            float(confianca_extracao),
            json.dumps(dados_extraidos_json, ensure_ascii=False),
            status_processamento.strip().upper(),
            erro_mensagem,
            agora
        ))
        return cursor.lastrowid


def listar_documentos_lote(batch_hash: str) -> list[dict[str, Any]]:
    """Retorna todos os documentos comprobatórios associados ao lote."""
    with get_acid_connection(write_lock=False) as conn:
        rows = conn.execute("""
            SELECT id, batch_hash, hash_arquivo_sha256, nome_arquivo_original,
                   tamanho_bytes, mime_type, tipo_documento, chave_acesso,
                   metodo_extracao, confianca_extracao, dados_extraidos_json,
                   status_processamento, erro_mensagem, criado_em
            FROM documentos_notas_fiscais
            WHERE batch_hash = ?
            ORDER BY id ASC
        """, (batch_hash,)).fetchall()
        docs = []
        for r in rows:
            d = dict(r)
            try:
                d["dados_extraidos_json"] = json.loads(d["dados_extraidos_json"])
            except Exception:
                pass
            docs.append(d)
        return docs


def obter_documento_por_hash_arquivo(hash_arquivo_sha256: str) -> dict[str, Any] | None:
    """Busca documento por hash SHA-256 do arquivo (antifraude de reenvio do mesmo PDF)."""
    with get_acid_connection(write_lock=False) as conn:
        row = conn.execute("""
            SELECT id, batch_hash, hash_arquivo_sha256, nome_arquivo_original,
                   tamanho_bytes, mime_type, tipo_documento, chave_acesso,
                   metodo_extracao, confianca_extracao, dados_extraidos_json,
                   status_processamento, erro_mensagem, criado_em
            FROM documentos_notas_fiscais
            WHERE hash_arquivo_sha256 = ?
            ORDER BY id DESC LIMIT 1
        """, (hash_arquivo_sha256,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["dados_extraidos_json"] = json.loads(d["dados_extraidos_json"])
        except Exception:
            pass
        return d


def obter_documento_por_chave_acesso(chave_acesso: str) -> dict[str, Any] | None:
    """Busca documento por chave de acesso de 44 dígitos da NF-e."""
    with get_acid_connection(write_lock=False) as conn:
        row = conn.execute("""
            SELECT id, batch_hash, hash_arquivo_sha256, nome_arquivo_original,
                   tamanho_bytes, mime_type, tipo_documento, chave_acesso,
                   metodo_extracao, confianca_extracao, dados_extraidos_json,
                   status_processamento, erro_mensagem, criado_em
            FROM documentos_notas_fiscais
            WHERE chave_acesso = ?
            ORDER BY id DESC LIMIT 1
        """, (chave_acesso.strip(),)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["dados_extraidos_json"] = json.loads(d["dados_extraidos_json"])
        except Exception:
            pass
        return d



def carregar_titulos_liquidados_db() -> list[dict[str, Any]]:
    """Lê todos os títulos comprados no SQLite para sincronizar o StockIndex no Startup."""
    with get_acid_connection(write_lock=False) as conn:
        rows = conn.execute("SELECT * FROM titulos_adquiridos").fetchall()
        return [dict(r) for r in rows]


def listar_historico_operacoes(limite: int = 30) -> list[dict[str, Any]]:
    """Retorna o histórico de lotes simulados e liquidados para exibição no Front-end."""
    with get_acid_connection(write_lock=False) as conn:
        rows = conn.execute("""
            SELECT batch_hash, criado_em, liquidado_em, cedente_nome, cedente_doc,
                   data_base_utilizada, taxa_mensal, total_notas, qtd_aprovadas,
                   qtd_recusadas, valor_bruto_total, valor_liquido_aprovado,
                   ganho_otimizador, status_operacao
            FROM lotes_operacoes
            ORDER BY criado_em DESC
            LIMIT ?
        """, (limite,)).fetchall()
        return [dict(r) for r in rows]


def registrar_auditoria_validadores(
    usuario_email: str,
    acao: str,
    regras_ativas_count: int,
    json_anterior: dict[str, Any] | list[Any],
    json_novo: dict[str, Any] | list[Any]
):
    """Registra log imutável de alterações feitas no validadores_antecipe.json."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_acid_connection(write_lock=True) as conn:
        conn.execute("""
            INSERT INTO auditoria_regras (
                criado_em, usuario_email, acao, regras_ativas_count, json_anterior, json_novo
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            agora,
            usuario_email,
            acao,
            regras_ativas_count,
            json.dumps(json_anterior, ensure_ascii=False),
            json.dumps(json_novo, ensure_ascii=False)
        ))


def listar_auditoria_validadores(limite: int = 20) -> list[dict[str, Any]]:
    """Retorna as alterações de regras em ordem decrescente."""
    with get_acid_connection(write_lock=False) as conn:
        rows = conn.execute("""
            SELECT id, criado_em, usuario_email, acao, regras_ativas_count
            FROM auditoria_regras
            ORDER BY id DESC
            LIMIT ?
        """, (limite,)).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Gestão de Identidade e Autenticação (Login)
# ---------------------------------------------------------------------------

def hash_senha(senha: str, salt: bytes | None = None) -> str:
    """Gera hash scrypt seguro com salt aleatório."""
    salt = salt or os.urandom(16)
    digest = hashlib.scrypt(senha.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def senha_confere(senha: str, guardado: str) -> bool:
    """Confere a senha contra o hash scrypt em tempo constante (anti-timing attack)."""
    try:
        partes = guardado.split("$")
        if len(partes) != 3 or partes[0] != "scrypt":
            return False
        salt = bytes.fromhex(partes[1])
        esperado = bytes.fromhex(partes[2])
        digest = hashlib.scrypt(senha.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(digest, esperado)
    except Exception:
        return False


_HASH_FALSO = hash_senha("usuario-inexistente-timing-attack-protection")


def salvar_usuario(email: str, senha: str, nome: str, cargo: str, role: str) -> None:
    """Cria o usuário ou atualiza senha/dados caso o email já exista (Upsert)."""
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_acid_connection(write_lock=True) as conn:
        conn.execute("""
            INSERT INTO usuarios (email, senha_hash, nome, cargo, role, criado_em)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
                senha_hash = excluded.senha_hash,
                nome = excluded.nome,
                cargo = excluded.cargo,
                role = excluded.role
        """, (
            email.strip().lower(),
            hash_senha(senha),
            nome.strip(),
            cargo.strip(),
            role.strip().upper(),
            agora
        ))


def autenticar_usuario(email: str, senha: str) -> dict[str, Any] | None:
    """Valida as credenciais do usuário. Retorna dados do usuário (sem senha) ou None."""
    email_limpo = email.strip().lower()
    with get_acid_connection(write_lock=False) as conn:
        linha = conn.execute(
            "SELECT id, email, senha_hash, nome, cargo, role FROM usuarios WHERE email = ?",
            (email_limpo,)
        ).fetchone()

    hash_banco = linha["senha_hash"] if linha else _HASH_FALSO
    if not senha_confere(senha, hash_banco) or linha is None:
        return None

    usuario = dict(linha)
    usuario.pop("senha_hash", None)
    return usuario


def obter_usuario_por_email(email: str) -> dict[str, Any] | None:
    """Retorna dados públicos do usuário por e-mail."""
    with get_acid_connection(write_lock=False) as conn:
        linha = conn.execute(
            "SELECT id, email, nome, cargo, role FROM usuarios WHERE email = ?",
            (email.strip().lower(),)
        ).fetchone()
        return dict(linha) if linha else None


def obter_usuario_por_id(usuario_id: int) -> dict[str, Any] | None:
    """Retorna dados públicos do usuário por ID."""
    with get_acid_connection(write_lock=False) as conn:
        linha = conn.execute(
            "SELECT id, email, nome, cargo, role FROM usuarios WHERE id = ?",
            (usuario_id,)
        ).fetchone()
        return dict(linha) if linha else None