# script_principal_turbo.py
# --------------------------------------------
# Leitura e transformação do PDF em DataFrame
# para o App Appolari Turbo.
#
# Requisitos:
#   - pdfplumber==0.11.0
#   - pdfminer.six==20231228
#   - pandas
#
# Exporta:
#   - processar_pdf(uploaded_file) -> pd.DataFrame
# --------------------------------------------

from __future__ import annotations
from typing import List, Dict, Any, Optional
import io
import re
import pdfplumber
import pandas as pd

# --------- Configs & Helpers ---------

# nomes canônicos que usaremos internamente
COL_ITEM = "item"
COL_COD  = "Código PDF"
COL_DESC = "Descrição resumida PDF"
COL_UNID = "Unidade"
COL_QTD  = "Quantidade"

# colunas “do app” que podem não existir ainda
COL_QP1  = "QUANT PESQ (1)"
COL_VM   = "Valor médio do produto"
COL_STAT = "Status"
COL_MERC = "Descrição localidade / Mercado"
COL_FONT = "Fontes"

# mapeamentos de nomes de coluna comuns no PDF -> canônicos
ALIAS_MAP = {
    # código
    r"^(c[oó]d(igo)?|codigo|c[oó]d\.)$": COL_COD,
    # descrição
    r"^(descri[cç][aã]o|descr)$": COL_DESC,
    # unidade
    r"^(unid(ade)?|und|uni|un)$": COL_UNID,
    # quantidade
    r"^(qtd|quantidade|qtde)$": COL_QTD,
    # item
    r"^(item|n[oº]?\s*item)$": COL_ITEM,
}

# detecta separador “forte” para linhas de texto soltas
MULTI_SPACE = re.compile(r"\s{2,}")

def _normalize_header(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())

def _canonicalize_header(h: str) -> str:
    h_norm = _normalize_header(h)
    for patt, target in ALIAS_MAP.items():
        if re.match(patt, h_norm, flags=re.IGNORECASE):
            return target
    # se não encontrou match, devolve o original capitalizado simples
    return h.strip()

def _coerce_int(x) -> Optional[int]:
    if x is None:
        return None
    if isinstance(x, (int,)):
        return int(x)
    s = str(x).strip()
    s = s.replace(".", "").replace(",", ".")  # tolera 1.000 e 1,0
    # remove quaisquer não-numéricos no fim/início
    s = re.sub(r"[^0-9\.\-]", "", s)
    if s == "" or s == "-" or s == ".":
        return None
    try:
        # se tem ponto, pode ser float; mas nossa qtd é int
        f = float(s)
        return int(round(f))
    except Exception:
        return None

def _first_not_null(*vals):
    for v in vals:
        if v not in (None, "", float("nan")):
            return v
    return None

# --------- Parse de Tabelas (pdfplumber) ---------

def _extract_tables(plumb: pdfplumber.PDF) -> List[pd.DataFrame]:
    """Extrai tabelas de todas as páginas em DataFrames."""
    dfs: List[pd.DataFrame] = []
    for page in plumb.pages:
        try:
            tables = page.extract_tables()
        except Exception:
            tables = None
        if not tables:
            continue
        for t in tables:
            if not t or len(t) < 2:
                continue
            # primeira linha como header
            header = [str(x or "").strip() for x in t[0]]
            rows = t[1:]
            if all(not any(r) for r in rows):
                continue
            df = pd.DataFrame(rows, columns=header)
            dfs.append(df)
    return dfs

def _rename_like(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza nomes de colunas para os canônicos quando possível."""
    new_cols = {}
    for c in df.columns:
        new_cols[c] = _canonicalize_header(str(c))
    df = df.rename(columns=new_cols)
    return df

def _pick_relevant_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Mantém/renomeia colunas principais; tenta derivar faltantes."""
    df = _rename_like(df)

    # Cria colunas que não existem, vazias
    for col in [COL_ITEM, COL_COD, COL_DESC, COL_UNID, COL_QTD]:
        if col not in df.columns:
            df[col] = None

    # tenta deduzir valores quando há colunas alternativas
    # (ex.: se existe "Descrição" com outro nome, já foi renomeado)

    # Normalizações específicas
    # item como inteiro (quando existir)
    df[COL_ITEM] = df[COL_ITEM].apply(lambda x: _coerce_int(x))

    # quantidade como inteiro
    df[COL_QTD] = df[COL_QTD].apply(lambda x: _coerce_int(x))

    # Unidades: limpamos abreviações simples
    def norm_unid(x):
        s = str(x or "").strip().upper()
        # normalizações comuns
        if s in ("UNID", "UND", "UNI", "UN."):
            return "UN"
        return s or None
    df[COL_UNID] = df[COL_UNID].apply(norm_unid)

    # Descrição: compacta espaços
    df[COL_DESC] = df[COL_DESC].apply(lambda x: re.sub(r"\s+", " ", str(x or "").strip()))

    # Código: remove espaços estranhos
    df[COL_COD] = df[COL_COD].apply(lambda x: str(x or "").strip())

    # remove linhas completamente vazias
    base_cols = [COL_DESC, COL_UNID, COL_QTD]
    df = df[~(df[base_cols].isna().all(axis=1))].copy()

    return df[[COL_ITEM, COL_COD, COL_DESC, COL_UNID, COL_QTD]]

# --------- Parse de Texto Corrido (fallback) ---------

def _extract_text_rows(plumb: pdfplumber.PDF) -> List[List[str]]:
    """
    Fallback quando não há tabela estruturada.
    Heurística: pega linhas de texto e tenta split por múltiplos espaços.
    Formato alvo (flexível): item | código | descrição | unidade | quantidade
    """
    linhas: List[str] = []
    for page in plumb.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        for raw in txt.splitlines():
            s = raw.strip()
            if not s:
                continue
            linhas.append(s)

    rows: List[List[str]] = []
    for s in linhas:
        # split por espaços múltiplos
        partes = MULTI_SPACE.split(s)
        partes = [p.strip() for p in partes if p.strip() != ""]
        # heurística: manter linhas com pelo menos 3 “colunas”
        if len(partes) >= 3:
            rows.append(partes)
    return rows

def _rows_to_df_guess(rows: List[List[str]]) -> pd.DataFrame:
    """
    Converte linhas em DF tentando identificar as 5 colunas alvo.
    Heurística: pega os últimos tokens como [unidade, quantidade] quando possível,
    primeiro token como item/código se for dígito, resto vira descrição.
    """
    registros: List[Dict[str, Any]] = []
    for r in rows:
        item_val: Optional[int] = None
        cod_val: str = ""
        desc_val: str = ""
        un_val: str = ""
        qtd_val: Optional[int] = None

        parts = r[:]

        # tenta quantidade no último token
        if parts:
            qtd_try = _coerce_int(parts[-1])
            if qtd_try is not None:
                qtd_val = qtd_try
                parts = parts[:-1]

        # tenta unidade no penúltimo token (abreviações curtas)
        if parts:
            penult = parts[-1].upper()
            if re.fullmatch(r"[A-Z\.]{1,5}", penult):
                un_val = penult
                parts = parts[:-1]

        # item/código no primeiro token se numérico
        if parts:
            maybe_item = _coerce_int(parts[0])
            if maybe_item is not None:
                item_val = maybe_item
                parts = parts[1:]
            # tenta código se sobrar algo pequeno tipo “123-ABC”
            if parts:
                first = parts[0]
                if re.match(r"^[0-9A-Za-z\-\./]{3,}$", first) and len(first) <= 20:
                    # só considera código se descrição não ficar vazia
                    cod_val = first
                    parts = parts[1:]

        desc_val = " ".join(parts).strip()

        # registra se ao menos descrição existe
        if desc_val:
            registros.append({
                COL_ITEM: item_val,
                COL_COD:  cod_val,
                COL_DESC: desc_val,
                COL_UNID: un_val or None,
                COL_QTD:  qtd_val,
            })

    if not registros:
        return pd.DataFrame(columns=[COL_ITEM, COL_COD, COL_DESC, COL_UNID, COL_QTD])
    df = pd.DataFrame(registros)
    # normaliza como no caminho de tabela
    df = _pick_relevant_columns(df)
    return df

# --------- Função pública ---------

def processar_pdf(uploaded_file: io.BytesIO) -> pd.DataFrame:
    """
    Lê o PDF (arquivo enviado pelo Streamlit) e retorna um DataFrame
    com as colunas exigidas pelo app.

    Retorna DataFrame vazio se não conseguir extrair nada útil.
    """
    if uploaded_file is None:
        return pd.DataFrame(columns=[COL_ITEM, COL_COD, COL_DESC, COL_UNID, COL_QTD])

    # Abrir o PDF
    try:
        # uploaded_file é um UploadedFile do Streamlit; .read() dá bytes
        # Mas pdfplumber aceita file-like; vamos garantir BytesIO
        file_bytes = uploaded_file.read() if hasattr(uploaded_file, "read") else uploaded_file
        if isinstance(file_bytes, (bytes, bytearray)):
            bio = io.BytesIO(file_bytes)
        else:
            bio = uploaded_file  # já é file-like
        bio.seek(0)
        pdf = pdfplumber.open(bio)
    except Exception:
        return pd.DataFrame(columns=[COL_ITEM, COL_COD, COL_DESC, COL_UNID, COL_QTD])

    # 1) Tenta tabelas
    try:
        table_dfs = _extract_tables(pdf)
    except Exception:
        table_dfs = []

    base_df = pd.DataFrame(columns=[COL_ITEM, COL_COD, COL_DESC, COL_UNID, COL_QTD])

    if table_dfs:
        parsed: List[pd.DataFrame] = []
        for raw_df in table_dfs:
            try:
                df_clean = _pick_relevant_columns(raw_df)
                if not df_clean.empty:
                    parsed.append(df_clean)
            except Exception:
                continue
        if parsed:
            base_df = pd.concat(parsed, ignore_index=True)

    # 2) Se tabelas falharam/ficaram vazias, tenta texto corrido
    if base_df.empty:
        try:
            rows = _extract_text_rows(pdf)
            base_df = _rows_to_df_guess(rows)
        except Exception:
            base_df = pd.DataFrame(columns=[COL_ITEM, COL_COD, COL_DESC, COL_UNID, COL_QTD])

    # Fecha o PDF
    try:
        pdf.close()
    except Exception:
        pass

    # Pós-processamento mínimo
    if base_df.empty:
        # retorna vazio já com colunas esperadas do app
        out = pd.DataFrame(columns=[
            COL_ITEM, COL_COD, COL_DESC, COL_UNID, COL_QTD,
            COL_QP1, COL_VM, COL_STAT, COL_MERC, COL_FONT
        ])
        return out

    # Garante QUANT PESQ (1) = 1
    base_df[COL_QP1] = 1

    # Garante colunas do app (se ainda não existirem)
    if COL_VM not in base_df.columns:
        base_df[COL_VM] = None
    if COL_STAT not in base_df.columns:
        base_df[COL_STAT] = ""
    if COL_MERC not in base_df.columns:
        base_df[COL_MERC] = ""
    if COL_FONT not in base_df.columns:
        base_df[COL_FONT] = ""

    # Ordena colunas na ordem preferida
    ordem = [
        COL_ITEM, COL_COD, COL_DESC, COL_UNID, COL_QTD,
        COL_QP1, COL_VM, COL_STAT, COL_MERC, COL_FONT
    ]
    cols = [c for c in ordem if c in base_df.columns] + [c for c in base_df.columns if c not in ordem]
    base_df = base_df[cols].reset_index(drop=True)

    return base_df
