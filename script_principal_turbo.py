# script_principal_turbo.py
# ------------------------------------------------------------
# Lê um PDF a partir de bytes/BytesIO e extrai itens da cotação
# retornando um DataFrame com as colunas:
# ['item', 'Código PDF', 'Descrição resumida PDF', 'Unidade', 'Quantidade']
# ------------------------------------------------------------

from io import BytesIO
import re
from typing import Iterable, List, Tuple
import pdfplumber
import pandas as pd


# ======= Unidades aceitas (pode ampliar à vontade) =======
UNIDADES = [
    "UNIDADE", "UNID", "UN", "PECA", "PEÇA", "PC", "PECAS", "PEÇAS",
    "METRO", "M", "MM", "CM",
    "CENTO",
    "KG", "LITRO", "L", "CX", "CONJ", "ROL"
]

# Monta o grupo da regex de unidade dinamicamente para evitar erros de acentuação/casos
UNID_GRP = "|".join(sorted(set(UNIDADES), key=len, reverse=True))

# ======= Regex principal =======
# Exemplo típico de linha:
#  1   047.003.388  ADAPTADOR - DE EM PVC, COM UM FLANGE FIXO, ...  UNIDADE   84
LINHA_RE = re.compile(
    rf"""
    ^\s*
    (?P<item>\d+)\s+                                       # nro item
    (?P<codigo>\d{{2}}[.\s]?\d{{3}}[.\s]?\d{{3}})\s+        # código dd.ddd.ddd (tolerante a espaços)
    (?P<desc>.+?)\s+                                       # descrição (preguiçosa)
    (?P<unid>(?:{UNID_GRP}))\s+                            # unidade
    (?P<qtd>\d{{1,6}})\b                                   # quantidade inteira
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

# Limpeza leve da descrição (remove múltiplos espaços/pontuação solta)
def _limpa_desc(txt: str) -> str:
    t = re.sub(r"\s+", " ", txt)
    t = t.replace(" ,", ",").replace(" .", ".").strip(" -–—")
    return t.strip()


def _normaliza_unidade(u: str) -> str:
    u = (u or "").strip().upper()
    # Mapeamento simples para padronizar
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
    """Extrai texto de todas as páginas do PDF."""
    text_pages: List[str] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            # extração simples de texto; se precisar, dá para usar extract_words/tables depois
            text_pages.append(page.extract_text() or "")
    return "\n".join(text_pages)


def _parse_text(raw_text: str) -> pd.DataFrame:
    """Aplica a regex nas linhas e monta o DataFrame."""
    rows: List[Tuple[int, str, str, str, int]] = []

    for m in LINHA_RE.finditer(raw_text):
        item = int(m.group("item"))
        codigo = m.group("codigo")
        # normaliza código para dd.ddd.ddd
        codigo = re.sub(r"\s+", "", codigo)
        codigo = (
            f"{codigo[:2]}.{codigo[2:5]}.{codigo[5:]}"
            if re.fullmatch(r"\d{8}", re.sub(r"[.]", "", codigo))
            else codigo
        )

        desc = _limpa_desc(m.group("desc"))
        unid = _normaliza_unidade(m.group("unid"))
        qtd = int(m.group("qtd"))

        rows.append((item, codigo, desc, unid, qtd))

    if not rows:
        # Nenhum match – devolve DF vazio com as colunas esperadas
        return pd.DataFrame(
            columns=["item", "Código PDF", "Descrição resumida PDF", "Unidade", "Quantidade"]
        )

    df = pd.DataFrame(
        rows,
        columns=["item", "Código PDF", "Descrição resumida PDF", "Unidade", "Quantidade"],
    )

    # Ordena por item se fizer sentido
    try:
        df = df.sort_values(by=["item"]).reset_index(drop=True)
    except Exception:
        pass

    return df


def processar_pdf(entrada) -> pd.DataFrame:
    """
    Entrada pode ser:
      - BytesIO
      - bytes
      - objeto UploadedFile do Streamlit (tem .getvalue())
    Retorna DataFrame com colunas:
      ['item', 'Código PDF', 'Descrição resumida PDF', 'Unidade', 'Quantidade']
    """
    # Normaliza a entrada para bytes
    if isinstance(entrada, BytesIO):
        pdf_bytes = entrada.getvalue()
    elif isinstance(entrada, (bytes, bytearray)):
        pdf_bytes = bytes(entrada)
    else:
        # Tenta .getvalue() (caso seja st.uploaded_file)
        try:
            pdf_bytes = entrada.getvalue()
        except Exception:
            raise ValueError("processar_pdf: tipo de entrada não suportado.")

    raw_text = _pdf_to_text(pdf_bytes)
    df = _parse_text(raw_text)

    return df
