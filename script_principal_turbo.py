# script_principal_turbo.py
# ------------------------------------------------------------
# Lê um PDF (bytes / BytesIO / UploadedFile) e extrai itens de cotação
# Retorna DataFrame com:
# ['item', 'Código PDF', 'Descrição resumida PDF', 'Unidade', 'Quantidade']
# ------------------------------------------------------------

from io import BytesIO
import re
from typing import List, Tuple
import pdfplumber
import pandas as pd

# ======= Unidades aceitas (pode ampliar) =======
UNIDADES = [
    "UNIDADE", "UNID", "UN", "PECA", "PEÇA", "PC", "PECAS", "PEÇAS",
    "METRO", "M", "MM", "CM",
    "CENTO",
    "KG", "LITRO", "L", "CX", "CONJ", "ROL"
]
UNID_GRP = "|".join(sorted(set(UNIDADES), key=len, reverse=True))

# ======= Regex principal (AGORA 3-3-3) =======
# Ex.: "1   047.003.388  ADAPTADOR ...  UNIDADE   84"
LINHA_RE = re.compile(
    rf"""
    ^\s*
    (?P<item>\d+)\s+                                       # nº item
    (?P<codigo>\d{{3}}[.\s]?\d{{3}}[.\s]?\d{{3}})\s+        # CÓDIGO ddd.ddd.ddd
    (?P<desc>.+?)\s+                                       # descrição (preguiçosa)
    (?P<unid>(?:{UNID_GRP}))\s+                            # unidade
    (?P<qtd>\d{{1,6}})\b                                   # quantidade
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

def _limpa_desc(txt: str) -> str:
    t = re.sub(r"\s+", " ", txt)
    t = t.replace(" ,", ",").replace(" .", ".").strip(" -–—")
    return t.strip()

def _normaliza_unidade(u: str) -> str:
    u = (u or "").strip().upper()
    mapa = {
        "UN": "UNIDADE",
        "UNID": "UNIDADE",
        "PECA": "PECA",
        "PEÇAS": "PECA",
        "PECAS": "PECA",
        "PC": "PECA",
        "M": "METRO",
    }
    return mapa.get(u, u)

def _pdf_to_text(pdf_bytes: bytes) -> str:
    pages: List[str] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for pg in pdf.pages:
            pages.append(pg.extract_text() or "")
    return "\n".join(pages)

def _parse_text(raw_text: str) -> pd.DataFrame:
    linhas: List[Tuple[int, str, str, str, int]] = []

    for m in LINHA_RE.finditer(raw_text):
        item = int(m.group("item"))
        codigo = m.group("codigo")

        # normaliza: remove espaços e garante formato ddd.ddd.ddd
        sem_pontos = re.sub(r"[.\s]", "", codigo)
        if re.fullmatch(r"\d{9}", sem_pontos):
            codigo = f"{sem_pontos[0:3]}.{sem_pontos[3:6]}.{sem_pontos[6:9]}"

        desc = _limpa_desc(m.group("desc"))
        unid = _normaliza_unidade(m.group("unid"))
        qtd = int(m.group("qtd"))

        linhas.append((item, codigo, desc, unid, qtd))

    if not linhas:
        return pd.DataFrame(
            columns=["item", "Código PDF", "Descrição resumida PDF", "Unidade", "Quantidade"]
        )

    df = pd.DataFrame(
        linhas,
        columns=["item", "Código PDF", "Descrição resumida PDF", "Unidade", "Quantidade"],
    )

    try:
        df = df.sort_values(by="item").reset_index(drop=True)
    except Exception:
        pass
    return df

def processar_pdf(entrada) -> pd.DataFrame:
    """
    entrada: BytesIO | bytes | UploadedFile (streamlit)
    """
    if isinstance(entrada, BytesIO):
        pdf_bytes = entrada.getvalue()
    elif isinstance(entrada, (bytes, bytearray)):
        pdf_bytes = bytes(entrada)
    else:
        try:
            pdf_bytes = entrada.getvalue()
        except Exception:
            raise ValueError("processar_pdf: tipo de entrada não suportado.")

    texto = _pdf_to_text(pdf_bytes)
    df = _parse_text(texto)
    return df
