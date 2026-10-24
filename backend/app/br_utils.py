"""Parse e formatação no padrão brasileiro (valores, datas, prazos e dias úteis)."""

from __future__ import annotations

import math
import re
from datetime import date, timedelta

_RE_NAO_NUMERICO = re.compile(r"[^0-9,.\-]")


def parse_valor_br(texto: str | float | int | None) -> float:
    """Converte "1.500,50", "1500,50", "1500.50" ou "R$ 1.500,50" em float."""
    if isinstance(texto, (int, float)) and not isinstance(texto, bool):
        valor = float(texto)
    else:
        bruto = str(texto or "").strip()
        s = _RE_NAO_NUMERICO.sub("", bruto)
        negativo = s.startswith("-")
        s = s.replace("-", "")
        if not s or not any(ch.isdigit() for ch in s):
            raise ValueError(f"valor inválido: {bruto!r}")
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                s = s.replace(".", "").replace(",", ".")  # 1.500,50
            else:
                s = s.replace(",", "")  # 1,500.50
        elif "," in s:
            s = s.replace(",", "") if s.count(",") > 1 else s.replace(",", ".")
        elif "." in s:
            partes = s.split(".")
            if len(partes) > 2 or len(partes[-1]) == 3:
                s = s.replace(".", "")  # 1.500 / 1.500.000 = separador de milhar
        valor = float(s)
        if negativo:
            valor = -valor
    if not math.isfinite(valor):
        raise ValueError(f"valor inválido: {texto!r}")
    return valor


def parse_data_br(texto: str | date | None) -> date:
    """Converte "22/10/2026", "2/1/2026", "22/10/26" ou ISO "2026-10-22" em date."""
    if isinstance(texto, date):
        return texto
    s = str(texto or "").strip().split(" ")[0].split("T")[0]
    if not s:
        raise ValueError("data vazia")
    try:
        if len(s) >= 8 and s[4] == "-":
            ano, mes, dia = s.split("-")
        else:
            partes = s.replace("-", "/").replace(".", "/").split("/")
            if len(partes) != 3:
                raise ValueError
            dia, mes, ano = partes
            if len(ano) == 2:
                ano = "20" + ano
        return date(int(ano), int(mes), int(dia))
    except ValueError:
        raise ValueError(f"data inválida: {texto!r}") from None


def formatar_data_br(data: date) -> str:
    return data.strftime("%d/%m/%Y")


def formatar_brl(valor: float) -> str:
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {texto}" if valor < 0 else f"R$ {texto}"


def formatar_percentual(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",") + "%"


def calcular_prazo_dias(data_vencimento: date, data_base: date) -> int:
    """Prazo em dias corridos entre a data-base da operação e o vencimento."""
    return (data_vencimento - data_base).days


def proximo_dia_util(data: date) -> date:
    """Próximo dia útil (segunda a sexta) estritamente posterior à data informada."""
    proxima = data + timedelta(days=1)
    while proxima.weekday() >= 5:
        proxima += timedelta(days=1)
    return proxima
