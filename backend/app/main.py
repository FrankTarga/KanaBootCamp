"""API REST do ANTECIPE PRO (FastAPI)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, File, Form, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api_schemas import BatchValidationResponse, ErroApi, HealthResponse, ValidadoresConfig
from .quant_analytics import formatar_data_br, parse_data_br
from .rule_engine import (
    CadastroSituacao,
    ErroArquivoLote,
    ErroConfiguracao,
    RuleEngine,
    carregar_config,
    validar_config,
)
from .stock_index import carregar_estoque

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s level=%(levelname)s logger=%(name)s %(message)s",
)
logger = logging.getLogger("antecipe.api")

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    estoque_path: Path
    validadores_path: Path
    cadastro_path: Path
    data_base_padrao: date | None
    max_upload_bytes: int
    cache_idempotencia: int


def carregar_settings() -> Settings:
    data_dir = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
    data_base_env = os.getenv("DATA_BASE_PADRAO", "").strip()
    return Settings(
        estoque_path=Path(os.getenv("ESTOQUE_PATH", str(data_dir / "estoque_antecipe.csv"))),
        validadores_path=Path(os.getenv("VALIDADORES_PATH", str(data_dir / "validadores_antecipe.json"))),
        cadastro_path=Path(os.getenv("SITUACAO_CADASTRAL_PATH", str(data_dir / "situacao_cadastral.json"))),
        data_base_padrao=parse_data_br(data_base_env) if data_base_env else None,
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024,
        cache_idempotencia=int(os.getenv("CACHE_IDEMPOTENCIA", "64")),
    )


class CacheIdempotencia:
    """LRU de respostas por (hash do arquivo, parâmetros, versão das regras)."""

    def __init__(self, capacidade: int):
        self._capacidade = capacidade
        self._dados: OrderedDict[tuple, BatchValidationResponse] = OrderedDict()
        self._lock = threading.Lock()

    def obter(self, chave: tuple) -> BatchValidationResponse | None:
        with self._lock:
            valor = self._dados.get(chave)
            if valor is not None:
                self._dados.move_to_end(chave)
            return valor

    def guardar(self, chave: tuple, valor: BatchValidationResponse) -> None:
        if self._capacidade <= 0:
            return
        with self._lock:
            self._dados[chave] = valor
            self._dados.move_to_end(chave)
            while len(self._dados) > self._capacidade:
                self._dados.popitem(last=False)


class ErroEntrada(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422, details: list[Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = carregar_settings()
    config = carregar_config(settings.validadores_path)
    index = carregar_estoque(
        settings.estoque_path, config.fundo.nome, config.fundo.cnpj, settings.data_base_padrao
    )
    app.state.settings = settings
    app.state.engine = RuleEngine(
        index, config, settings.validadores_path, CadastroSituacao(settings.cadastro_path)
    )
    app.state.cache = CacheIdempotencia(settings.cache_idempotencia)
    logger.info(
        "estoque carregado linhas=%s antecipe=%s fundos=%s patrimonio=%.2f data_base=%s tempo_ms=%s",
        index.total_linhas,
        index.linhas_antecipe,
        len(index.fundos),
        index.patrimonio_antecipe,
        formatar_data_br(index.data_base_padrao),
        index.tempo_carga_ms,
    )
    yield


app = FastAPI(
    title="ANTECIPE PRO",
    version="1.0.0",
    description="Motor de elegibilidade, precificação e anti-fraude do ANTECIPE FIDC.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Idempotent-Replay", "X-Request-ID"],
)


# ---------------------------------------------------------------------------
# Observabilidade e formato único de erro: {"error": {"code", "message", "details"}}
# ---------------------------------------------------------------------------

@app.middleware("http")
async def request_id_e_log(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    request.state.request_id = request_id
    inicio = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s duracao_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        (time.perf_counter() - inicio) * 1000,
    )
    return response


def _resposta_erro(status_code: int, code: str, message: str, details: list[Any] | None = None) -> JSONResponse:
    corpo = {"error": {"code": code, "message": message, "details": details or []}}
    return JSONResponse(status_code=status_code, content=corpo)


@app.exception_handler(ErroEntrada)
async def _erro_entrada(request: Request, exc: ErroEntrada):
    return _resposta_erro(exc.status_code, exc.code, exc.message, exc.details)


@app.exception_handler(ErroArquivoLote)
async def _erro_arquivo(request: Request, exc: ErroArquivoLote):
    return _resposta_erro(422, "ARQUIVO_INVALIDO", str(exc))


@app.exception_handler(ErroConfiguracao)
async def _erro_configuracao(request: Request, exc: ErroConfiguracao):
    return _resposta_erro(422, "CONFIGURACAO_INVALIDA", "A configuração de validadores é inválida.", exc.erros)


@app.exception_handler(RequestValidationError)
async def _erro_validacao(request: Request, exc: RequestValidationError):
    detalhes = [{"campo": ".".join(str(p) for p in e.get("loc", ())), "mensagem": e.get("msg", "")} for e in exc.errors()]
    return _resposta_erro(422, "REQUISICAO_INVALIDA", "Requisição inválida.", detalhes)


@app.exception_handler(StarletteHTTPException)
async def _erro_http(request: Request, exc: StarletteHTTPException):
    codigos = {404: "NAO_ENCONTRADO", 405: "METODO_NAO_PERMITIDO"}
    return _resposta_erro(exc.status_code, codigos.get(exc.status_code, f"HTTP_{exc.status_code}"), str(exc.detail))


@app.exception_handler(Exception)
async def _erro_interno(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "-")
    logger.exception("request_id=%s erro inesperado", request_id)
    return _resposta_erro(500, "ERRO_INTERNO", f"Erro inesperado. Informe o código {request_id} ao suporte.")


# ---------------------------------------------------------------------------
# Rotas /api/v1
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1", responses={422: {"model": ErroApi}, 500: {"model": ErroApi}})

_VERDADEIRO = {"true", "1", "sim", "s", "yes", "y", "on"}
_FALSO = {"false", "0", "nao", "não", "n", "no", "off"}


def _engine(request: Request) -> RuleEngine:
    return request.app.state.engine


def _parse_data_base(valor: str | None) -> date | None:
    if valor is None or not valor.strip():
        return None
    try:
        return parse_data_br(valor)
    except ValueError:
        raise ErroEntrada("DATA_BASE_INVALIDA", f"data_base '{valor}' inválida; use dd/mm/aaaa (ex.: 22/10/2026).") from None


def _parse_taxa(valor: str | None) -> float | None:
    if valor is None or not valor.strip():
        return None
    try:
        taxa = float(valor.strip().replace(",", "."))
    except ValueError:
        taxa = -1.0
    if not (0 <= taxa < 1):
        raise ErroEntrada(
            "TAXA_INVALIDA", f"taxa_mensal '{valor}' inválida; envie em decimal (ex.: 0.025 = 2,5% a.m.)."
        )
    return taxa


def _parse_bool(valor: str | None, padrao: bool) -> bool:
    if valor is None or not valor.strip():
        return padrao
    texto = valor.strip().lower()
    if texto in _VERDADEIRO:
        return True
    if texto in _FALSO:
        return False
    raise ErroEntrada("OTIMIZAR_LOTE_INVALIDO", f"otimizar_lote '{valor}' inválido; use true ou false.")


def _parse_override(valor: str | None) -> tuple[ValidadoresConfig | None, str]:
    if valor is None or not valor.strip():
        return None, ""
    try:
        config = ValidadoresConfig.model_validate(json.loads(valor))
    except json.JSONDecodeError as exc:
        raise ErroEntrada("OVERRIDE_INVALIDO", f"validadores_override não é um JSON válido: {exc.msg}.") from None
    except ValidationError as exc:
        detalhes = [{"campo": ".".join(str(p) for p in e["loc"]), "mensagem": e["msg"]} for e in exc.errors()]
        raise ErroEntrada("OVERRIDE_INVALIDO", "validadores_override fora do schema.", details=detalhes) from None
    erros = validar_config(config)
    if erros:
        raise ErroEntrada("OVERRIDE_INVALIDO", "validadores_override tem regras inválidas.", details=erros)
    assinatura = hashlib.sha256(json.dumps(config.para_json(), sort_keys=True).encode()).hexdigest()
    return config, assinatura


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    engine = _engine(request)
    index = engine.index
    return HealthResponse(
        status="ready",
        data_base_padrao=formatar_data_br(index.data_base_padrao),
        estoque_total_linhas=index.total_linhas,
        estoque_antecipe_linhas=index.linhas_antecipe,
        patrimonio_antecipe_fidc=index.patrimonio_antecipe,
        fundos_monitorados=len(index.fundos),
        regras_ativas_count=engine.regras_ativas_count(),
        tempo_carga_estoque_ms=index.tempo_carga_ms,
        versao_config=engine.versao_config,
    )


@router.get("/validators", response_model=ValidadoresConfig, response_model_exclude_unset=True)
def obter_validadores(request: Request) -> ValidadoresConfig:
    return _engine(request).config


@router.put("/validators", response_model=ValidadoresConfig, response_model_exclude_unset=True)
def atualizar_validadores(config: ValidadoresConfig, request: Request) -> ValidadoresConfig:
    try:
        return _engine(request).atualizar_config(config)
    except OSError:
        logger.exception("falha ao persistir validadores")
        raise ErroEntrada(
            "FALHA_PERSISTENCIA", "Não foi possível salvar validadores_antecipe.json; nada foi alterado.", 500
        ) from None


@router.post("/batches/validate", response_model=BatchValidationResponse)
def validar_lote(
    request: Request,
    response: Response,
    file: UploadFile = File(..., description="CSV do lote (;, decimal com vírgula, datas dd/mm/aaaa)"),
    data_base: str | None = Form(None, description="dd/mm/aaaa; padrão = data-base detectada no estoque"),
    taxa_mensal: str | None = Form(None, description="decimal, ex.: 0.025 = 2,5% a.m."),
    otimizar_lote: str | None = Form(None, description="true (padrão) ou false"),
    validadores_override: str | None = Form(None, description="JSON de validadores para simulação what-if (não persiste)"),
) -> BatchValidationResponse:
    settings: Settings = request.app.state.settings
    engine = _engine(request)

    conteudo = file.file.read(settings.max_upload_bytes + 1)
    if len(conteudo) > settings.max_upload_bytes:
        raise ErroEntrada(
            "ARQUIVO_GRANDE_DEMAIS", f"O arquivo passa do limite de {settings.max_upload_bytes // (1024 * 1024)} MB.", 413
        )
    if not conteudo.strip():
        raise ErroArquivoLote("O arquivo está vazio.")

    data = _parse_data_base(data_base)
    taxa = _parse_taxa(taxa_mensal)
    otimizar = _parse_bool(otimizar_lote, True)
    override, assinatura_override = _parse_override(validadores_override)

    chave = (
        hashlib.sha256(conteudo).hexdigest(),
        data.isoformat() if data else None,
        taxa,
        otimizar,
        engine.assinatura_estado(),
        assinatura_override,
    )
    cache: CacheIdempotencia = request.app.state.cache
    em_cache = cache.obter(chave)
    if em_cache is not None:
        response.headers["X-Idempotent-Replay"] = "true"
        return em_cache

    resultado = engine.validar_lote(conteudo, data, taxa, otimizar, override)
    cache.guardar(chave, resultado)
    response.headers["X-Idempotent-Replay"] = "false"
    logger.info(
        "request_id=%s lote=%s notas=%s aprovadas=%s ganho_otimizador=%.2f tempo_ms=%s",
        request.state.request_id,
        resultado.meta.batch_hash_idempotencia[:12],
        resultado.resumo.total_notas,
        resultado.resumo.qtd_aprovadas,
        resultado.meta.ganho_otimizador_reais,
        resultado.meta.tempo_processamento_ms,
    )
    return resultado


app.include_router(router)


@app.get("/", include_in_schema=False)
def raiz() -> dict[str, str]:
    return {"servico": "ANTECIPE PRO", "docs": "/docs", "health": "/api/v1/health"}
