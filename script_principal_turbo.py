# script_principal_turbo.py
# ------------------------------------------------------------
# Lê um PDF (bytes / BytesIO / UploadedFile) e extrai itens de cotação.
# Retorna DataFrame com colunas:
# ['item', 'Código PDF', 'Descrição resumida PDF', 'Unidade', 'Quantidade']
# ------------------------------------------------------------
from __future__ import annotations

from io import BytesIO
from typing import List, Tuple

import pandas as pd
import pdfplumber
import re

# observabilidade opcional (no-op se não existir)
try:
    from observability import notify_error  # type: ignore
except Exception:  # pragma: no cover
    def notify_error(_step: str, exc: BaseException | None = None, **_kw) -> None:
        return None

# ======= Unidades aceitas (pode ampliar) =======
UNIDADES = [
    "UNIDADE",
    "UNID",
    "UN",
    "PECA",
    "PEÇA",
    "PC",
    "PECAS",
    "PEÇAS",
    "METRO",
    "M",
    "MM",
    "CM",
    "CENTO",
    "KG",
    "LITRO",
    "L",
    "CX",
    "CONJ",
    "ROL",
]
UNID_GRP = "|".join(sorted(set(UNIDADES), key=len, reverse=True))

# ======= Regex principal (3-3-3 para código) =======
# Ex.: "1   047.003.388  ADAPTADOR ...  UNIDADE   84"
LINHA_RE = re.compile(
    rf"""
    ^\s*
    (?P<item>\d+)\s+                                       # nº do item
    (?P<codigo>\d{{3}}[.\s]?\d{{3}}[.\s]?\d{{3}})\s+        # código ddd.ddd.ddd (ou com espaços)
    (?P<desc>.+?)\s+                                       # descrição (lazy)
    (?P<unid>(?:{UNID_GRP}))\s+                            # unidade
    (?P<qtd>\d{{1,6}})\b                                   # quantidade
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

COLS_SAIDA = ["item", "Código PDF", "Descrição resumida PDF", "Unidade", "Quantidade"]


def _df_vazio() -> pd.DataFrame:
    return pd.DataFrame(columns=COLS_SAIDA)


def _limpa_desc(txt: str) -> str:
    """Normaliza espaços e pontuação básica."""
    t = re.sub(r"\s+", " ", str(txt))
    t = t.replace(" ,", ",").replace(" .", ".").strip(" -–—")
    return t.strip()


def _normaliza_unidade(u: str) -> str:
    """Converte abreviações para forma canônica."""
    u = (u or "").strip().upper()
    mapa = {"UN": "UNIDADE", "UNID": "UNIDADE", "PECA": "PECA", "PEÇAS": "PECA", "PECAS": "PECA", "PC": "PECA", "M": "METRO"}
    return mapa.get(u, u)


def _formata_codigo_ddd(codigo: str) -> str:
    """
    Remove pontos/espaços e retorna no formato ddd.ddd.ddd quando possível.
    """
    sem_pontos = re.sub(r"[.\s]", "", str(codigo))
    if re.fullmatch(r"\d{9}", sem_pontos):
        return f"{sem_pontos[0:3]}.{sem_pontos[3:6]}.{sem_pontos[6:9]}"
    return codigo


def _pdf_to_text(pdf_bytes: bytes) -> str:
    """Extrai texto de todas as páginas com pdfplumber."""
    pages: List[str] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for pg in pdf.pages:
            pages.append(pg.extract_text() or "")
    return "\n".join(pages).strip()


def _parse_text(raw_text: str) -> pd.DataFrame:
    """Aplica o regex de linhas ao texto completo e monta o DataFrame."""
    if not raw_text:
        return _df_vazio()

    linhas: List[Tuple[int, str, str, str, int]] = []

    for m in LINHA_RE.finditer(raw_text):
        try:
            item = int(m.group("item"))
            codigo = _formata_codigo_ddd(m.group("codigo"))
            desc = _limpa_desc(m.group("desc"))
            unid = _normaliza_unidade(m.group("unid"))
            qtd = int(m.group("qtd"))
            linhas.append((item, codigo, desc, unid, qtd))
        except Exception as exc:  # ignora linhas quebradas sem abortar tudo
            notify_error("parse_linha", exc=exc)

    if not linhas:
        return _df_vazio()

    df = pd.DataFrame(linhas, columns=COLS_SAIDA)
    try:
        df = df.sort_values(by="item").reset_index(drop=True)
    except Exception:
        pass
    return df


def processar_pdf(entrada) -> pd.DataFrame:
    """
    Lê um PDF (BytesIO | bytes | UploadedFile) e retorna DataFrame com os itens.
    Colunas: ['item', 'Código PDF', 'Descrição resumida PDF', 'Unidade', 'Quantidade']
    """
    # obtém os bytes do PDF a partir do tipo recebido
    try:
        if isinstance(entrada, BytesIO):
            pdf_bytes = entrada.getvalue()
        elif isinstance(entrada, (bytes, bytearray)):
            pdf_bytes = bytes(entrada)
        else:
            # ex.: streamlit UploadedFile
            pdf_bytes = entrada.getvalue()
    except Exception as exc:
        notify_error("entrada_invalida", exc=exc)
        raise ValueError("processar_pdf: tipo de entrada não suportado.") from exc

    try:
        texto = _pdf_to_text(pdf_bytes)
    except Exception as exc:
        notify_error("pdf_to_text", exc=exc)
        # se não conseguiu extrair texto, retorna DF vazio (não quebra o app)
        return _df_vazio()

    try:
        return _parse_text(texto)
    except Exception as exc:
        notify_error("parse_text", exc=exc)
        return _df_vazio()
