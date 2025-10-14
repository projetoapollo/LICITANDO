# price_search.py
# Consulta de preços no catálogo local data/catalogo_precos.csv
# Compatível com preço usando vírgula ou ponto como separador decimal.

from __future__ import annotations
import os
import math
import pandas as pd
from functools import lru_cache
from typing import Optional, Tuple, List

CATALOGO_PATH = os.path.join("data", "catalogo_precos.csv")

# ---------------------------------------------
# Utilidades
# ---------------------------------------------
def _to_float_any(price) -> Optional[float]:
    """
    Converte string de preço em float aceitando formatos:
    - "2,90"  => 2.90
    - "2.90"  => 2.90
    - "1.234,56" => 1234.56
    - "1,234.56" => 1234.56
    Retorna None se não conseguir converter.
    """
    if price is None or (isinstance(price, float) and math.isnan(price)):
        return None

    if isinstance(price, (int, float)):
        return float(price)

    s = str(price).strip()
    if not s:
        return None

    # Se contém vírgula, assumimos estilo “brasileiro” e removemos separadores de milhar.
    if "," in s:
        s = s.replace(".", "")  # remove milhar
        s = s.replace(",", ".")  # vírgula decimal -> ponto

    # Caso contrário, já deve estar em estilo “ponto decimal”.
    try:
        return float(s)
    except Exception:
        return None


def _norm_text(x: str) -> str:
    return " ".join(str(x).strip().upper().split())


# ---------------------------------------------
# Leitura do catálogo (com cache)
# ---------------------------------------------
@lru_cache(maxsize=1)
def load_catalogo() -> pd.DataFrame:
    """
    Lê data/catalogo_precos.csv com cabeçalho:
    descricao,unidade,preco,mercado,fonte,codigo
    Faz limpeza de textos e conversão de preço para float.
    """
    if not os.path.exists(CATALOGO_PATH):
        # retorna DF vazio com colunas esperadas
        return pd.DataFrame(
            columns=["descricao", "unidade", "preco", "mercado", "fonte", "codigo"]
        )

    df = pd.read_csv(CATALOGO_PATH, dtype=str, keep_default_na=False)
    # Garante colunas
    for col in ["descricao", "unidade", "preco", "mercado", "fonte", "codigo"]:
        if col not in df.columns:
            df[col] = ""

    # Normalizações
    df["descricao_norm"] = df["descricao"].map(_norm_text)
    df["unidade_norm"] = df["unidade"].map(_norm_text)
    df["codigo_norm"] = df["codigo"].map(lambda x: _norm_text(x).replace(" ", ""))  # remove espaços
    df["preco_float"] = df["preco"].map(_to_float_any)

    # Remove linhas sem preço válido
    df = df[~df["preco_float"].isna()].copy()

    return df


# ---------------------------------------------
# Matching e agregação
# ---------------------------------------------
def _match_por_codigo(catalogo: pd.DataFrame, codigo_pdf: str) -> pd.DataFrame:
    cod = _norm_text(codigo_pdf).replace(" ", "")
    if not cod:
        return catalogo.iloc[0:0]
    return catalogo.loc[catalogo["codigo_norm"] == cod]


def _match_por_descricao(catalogo: pd.DataFrame, desc_pdf: str) -> pd.DataFrame:
    """
    Fallback simples: contém todos os termos da descrição (normalizada).
    """
    desc = _norm_text(desc_pdf)
    if not desc:
        return catalogo.iloc[0:0]

    termos = [t for t in desc.split() if len(t) >= 3]  # ignora termos mto curtos
    if not termos:
        return catalogo.iloc[0:0]

    mask = pd.Series(True, index=catalogo.index)
    for t in termos:
        mask &= catalogo["descricao_norm"].str.contains(t, na=False)

    return catalogo[mask]


def _agregar_resultados(df_matches: pd.DataFrame) -> Tuple[Optional[float], str, str]:
    """
    Calcula média de preço + compõe campos Mercado e Fonte (únicos, separados por '; ').
    """
    if df_matches.empty:
        return None, "", ""

    media = df_matches["preco_float"].mean()

    # Juntar mercados e fontes distintos
    mercados = (
        df_matches["mercado"]
        .fillna("")
        .map(str)
        .map(str.strip)
        .replace("", pd.NA)
        .dropna()
        .unique()
    )
    fontes = (
        df_matches["fonte"]
        .fillna("")
        .map(str)
        .map(str.strip)
        .replace("", pd.NA)
        .dropna()
        .unique()
    )

    mercados_str = "; ".join(mercados) if len(mercados) else ""
    fontes_str = "; ".join(fontes) if len(fontes) else ""

    return float(media), mercados_str, fontes_str


# ---------------------------------------------
# API pública usada pelo app
# ---------------------------------------------
def aplicar_catalogo_em_df(df_itens: pd.DataFrame) -> pd.DataFrame:
    """
    Recebe o DataFrame extraído do PDF (com colunas como 'Código PDF', 'Descrição resumida PDF', 'Unidade')
    e preenche:
        - 'Valor médio do produto'
        - 'Descrição localidade / Mercado'
        - 'Fontes'
    Retorna uma CÓPIA do DF com as colunas novas.
    """
    df = df_itens.copy()

    # Garante colunas de saída
    if "Valor médio do produto" not in df.columns:
        df["Valor médio do produto"] = pd.NA
    if "Descrição localidade / Mercado" not in df.columns:
        df["Descrição localidade / Mercado"] = pd.NA
    if "Fontes" not in df.columns:
        df["Fontes"] = pd.NA

    catalogo = load_catalogo()

    # Se catálogo estiver vazio, só devolvemos o DF sem alterações
    if catalogo.empty:
        return df

    # Colunas de entrada (nomes conforme nosso app)
    col_codigo = None
    col_desc = None
    col_unid = None

    # tenta detectar nomes das colunas do app atual
    for c in df.columns:
        cn = c.lower()
        if col_codigo is None and ("código pdf" in cn or "codigo pdf" in cn or cn == "codigo"):
            col_codigo = c
        if col_desc is None and ("descrição resumida" in cn or "descricao resumida" in cn or "descrição" in cn or "descricao" in cn):
            col_desc = c
        if col_unid is None and ("unidade" in cn):
            col_unid = c

    # Preenchimento linha a linha (suficiente para o catálogo local)
    valores: List[Optional[float]] = []
    mercados_out: List[str] = []
    fontes_out: List[str] = []

    for _, row in df.iterrows():
        cod = str(row[col_codigo]) if col_codigo else ""
        desc = str(row[col_desc]) if col_desc else ""
        unid = str(row[col_unid]) if col_unid else ""

        # 1) tenta por código
        m = _match_por_codigo(catalogo, cod)
        if m.empty:
            # 2) fallback por descrição
            m = _match_por_descricao(catalogo, desc)

        media, mercados, fontes = _agregar_resultados(m)
        valores.append(None if media is None else round(media, 2))
        mercados_out.append(mercados)
        fontes_out.append(fontes)

    df["Valor médio do produto"] = valores
    df["Descrição localidade / Mercado"] = mercados_out
    df["Fontes"] = fontes_out

    return df


# Mantém um nome curto para integração com o app existente
def buscar_precos(df_itens: pd.DataFrame) -> pd.DataFrame:
    """
    Alias compatível com o app: retorna df com colunas de preço preenchidas.
    """
    return aplicar_catalogo_em_df(df_itens)


# Execução isolada para teste local rápido
if __name__ == "__main__":
    # Exemplo mínimo de teste (roda localmente se quiser)
    exemplo = pd.DataFrame({
        "Código PDF": ["047.003.388", "045.010.540"],
        "Descrição resumida PDF": ["ADAPTADOR PVC 3/4", "ANEL DE BORRACHA 3/4"],
        "Unidade": ["UNIDADE", "PECA"],
        "Quantidade": [84, 27]
    })
    out = aplicar_catalogo_em_df(exemplo)
    print(out)
