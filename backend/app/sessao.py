"""Token de sessão do portal: JSON assinado com HMAC-SHA256 e validade (stdlib, sem JWT).

Formato: <payload base64url>.<assinatura base64url>. Quem não tem o segredo não forja nem altera o perfil.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode()


def _de_b64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _assinar(segredo: bytes, payload: str) -> str:
    return _b64(hmac.new(segredo, payload.encode(), hashlib.sha256).digest())


def emitir_token(segredo: bytes, usuario: dict[str, Any], validade_s: int) -> str:
    payload = _b64(json.dumps({**usuario, "exp": int(time.time()) + validade_s}, ensure_ascii=False).encode())
    return f"{payload}.{_assinar(segredo, payload)}"


def ler_token(segredo: bytes, token: str) -> dict[str, Any] | None:
    """Usuário do token, ou None se a assinatura não bate, o formato é inválido ou venceu."""
    payload, _, assinatura = token.partition(".")
    if not assinatura or not hmac.compare_digest(assinatura, _assinar(segredo, payload)):
        return None
    try:
        dados = json.loads(_de_b64(payload))
    except ValueError:
        return None
    if not isinstance(dados, dict) or dados.pop("exp", 0) < time.time():
        return None
    return dados
