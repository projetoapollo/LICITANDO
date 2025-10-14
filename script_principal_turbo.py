# script_principal_turbo.py
from io import BytesIO
import re
import pdfplumber
import pandas as pd

# Regex para linhas do item (ajuste fino se seu PDF variar muito)
# Exemplo de linha (do seu print):
# 1   047.003.388  ADAPTADOR ... UNIDADE  84  ______
LINHA_RE = re.compile(
    r"""^\s*
        (?P<item>\d+)\s+                                   # nº item
        (?P<codigo>\d{3}\.\d{3}\.\d{3})\s+                 # código 000.000.000
        (?P<descricao>.+?)\s+                              # descrição (gananciosa, mas corta antes da unidade)
        (?P<unidade>(UNIDADE|METRO|PECA|PEÇA|CONJ|JOGO|KG|LITRO|CX|CENTO|ROL|M²|M³|M|MM|CM))\s+
        (?P<quantidade>\d+)\b                              # quantidade inteira
        """,
    re.IGNORECASE | re.VERBOSE,
)

UNIDADES_NORMALIZAR = {
    "PEÇA": "PECA",
    "M2": "M²",
    "M3": "M³",
}

def _normaliza_unidade(u: str) -> str:
    u = u.strip().upper()
    return UNIDADES_NORMALIZAR.get(u, u)

def _limpa_desc(desc: str) -> str:
    # Remove ruídos comuns no fim da linha (traços, sublinhados, etc.)
    desc = re.sub(r"(_+|-{2,})\s*$", "", desc).strip()
    return desc

def extrair_itens_pdf(pdf_bytes: bytes) -> pd.DataFrame:
    linhas = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            texto = page.extract_text() or ""
            for raw in texto.splitlines():
                m = LINHA_RE.match(raw)
                if m:
                    d = m.groupdict()
                    d["unidade"] = _normaliza_unidade(d["unidade"])
                    d["descricao"] = _limpa_desc(d["descricao"])
                    # Converte quantidade
                    try:
                        d["quantidade"] = int(d["quantidade"])
                    except:
                        pass
                    linhas.append(d)

    if not linhas:
        # Se nada foi extraído, ajuda a depurar
        raise ValueError(
            "Não consegui extrair itens do PDF. "
            "Verifique se o layout mudou ou me envie 1–2 páginas para ajustar o regex."
        )

    df = pd.DataFrame(linhas)[["item", "codigo", "descricao", "unidade", "quantidade"]]
    # Ordena pelo item, só para garantir
    df["item"] = pd.to_numeric(df["item"], errors="coerce")
    df = df.sort_values("item").reset_index(drop=True)
    return df

def processar_pdf(uploaded_file) -> tuple[pd.DataFrame, BytesIO]:
    """
    Recebe o arquivo do st.file_uploader (UploadedFile),
    retorna (DataFrame, BytesIO_excel).
    """
    pdf_bytes = uploaded_file.getvalue()
    df = extrair_itens_pdf(pdf_bytes)

    # Aqui você pode integrar seu buscador de preços depois.
    # Por enquanto, já devolvemos a planilha com as colunas básicas.
    # Se quiser manter as colunas do seu Excel anterior, adiciono abaixo:
    df_out = df.rename(columns={
        "codigo": "Código PDF",
        "descricao": "Descrição resumida PDF",
        "unidade": "Unidade",
        "quantidade": "Quantidade",
    })
    # Campos de preço/placeholders (opcional)
    df_out["Valor médio do produto"] = ""
    df_out["Status"] = ""
    df_out["Descrição localidade / Mercado"] = ""
    df_out["Fontes"] = ""

    # Gera Excel em memória
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        df_out.to_excel(writer, index=False, sheet_name="Cotacao_Final")
    out.seek(0)

    return df_out, out
