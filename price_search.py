# price_search.py
# ------------------------------------------------------------
# Busca preços no catálogo local (data/catalogo_precos.csv)
# para cada item extraído do PDF.
# ------------------------------------------------------------
from __future__ import annotations

import math
import os
import re
from typing import List, Tuple, Optional

import pandas as pd

# observabilidade opcional (guard e notify_error)
try:
    from observability import guard, notify_error  # type: ignore
except Exception:  # pragma: no cover
    def guard(_name: str):
        def deco(fn):
            return fn
        return deco

    def notify_error(_step: str, exc: BaseException | None = None, **_kw) -> None:
        return None

# Caminho fixo do catálogo
CATALOGO_ARQ = "data/catalogo_precos.csv"

# ------------------------------------------------------------
# Helpers de normalização / limpeza
# ------------------------------------------------------------
_SPACES = re.compile(r"\s+")
_PUNCTS = re.compile(r"[^\w\s]", flags=re.UNICODE)


def _norm_txt(txt: str) -> str:
    """Normaliza texto para comparação de tokens."""
    if not isinstance(txt, str):
        return ""
    txt = txt.lower()
    txt = _PUNCTS.sub(" ", txt)
    txt = _SPACES.sub(" ", txt).strip()
    return txt


def _token_set_overlap(a: str, b: str) -> float:
    """Similaridade Jaccard simples (0..1) entre conjuntos de tokens."""
    if not a or not b:
        return 0.0
    sa = set(_norm_txt(a).split())
    sb = set(_norm_txt(b).split())
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    uni = len(sa | sb)
    return inter / uni if uni else 0.0


def _to_float(x: object) -> float:
    """Converte string numérica para float (retorna NaN se falhar)."""
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return math.nan


def _carregar_catalogo(path: str = CATALOGO_ARQ) -> pd.DataFrame:
    """
    Lê o catálogo local. Espera colunas:
    descricao, unidade, preco, mercado, fonte, codigo
    """
    if not os.path.exists(path):
        return pd.DataFrame(columns=["descricao", "unidade", "preco", "mercado", "fonte", "codigo"])

    try:
        df = pd.read_csv(path, encoding="utf-8")
    except Exception as exc:
        notify_error("ler_catalogo", exc=exc)
        return pd.DataFrame(columns=["descricao", "unidade", "preco", "mercado", "fonte", "codigo"])

    for col in ["descricao", "unidade", "preco", "mercado", "fonte", "codigo"]:
        if col not in df.columns:
            df[col] = ""

    # normaliza tipos
    df = df.fillna("")
    df["descricao"] = df["descricao"].astype(str)
    df["unidade"] = df["unidade"].astype(str)
    df["mercado"] = df["mercado"].astype(str)
    df["fonte"] = df["fonte"].astype(str)
    df["codigo"] = df["codigo"].astype(str)
    df["preco"] = df["preco"].map(_to_float)

    # colunas auxiliares
    df["_desc_norm"] = df["descricao"].map(_norm_txt)
    df["_codigo_norm"] = df["codigo"].str.strip()
    return df


# ------------------------------------------------------------
# Função principal
# ------------------------------------------------------------
@guard("buscar_precos")
def buscar_precos(
    df: pd.DataFrame,
    min_score: float = 0.7,
    *,
    similaridade_minima: Optional[float] = None,
) -> Tuple[List[float], List[str], List[str]]:
    """
    Retorna 3 listas (mesma ordem do DF):
      - valores (média/preço encontrado por item)
      - mercados (descrição/localidade)
      - fontes (URL/nome da fonte)

    Regras:
      1) Se existir 'Código PDF', tenta casar por código (cat.codigo).
      2) Se não casar por código, tenta por similaridade de descrição
         ('Descrição resumida PDF' ~ cat.descricao) com limiar.
    """
    if similaridade_minima is not None:
        min_score = float(similaridade_minima)

    # se DF vazio → devolve NaN
    if df is None or df.empty:
        n = 0 if df is None else len(df)
        return [math.nan] * n, [""] * n, [""] * n

    catalogo = _carregar_catalogo(CATALOGO_ARQ)
    if catalogo.empty:
        return [math.nan] * len(df), [""] * len(df), [""] * len(df)

    tem_cod = "Código PDF" in df.columns
    tem_desc = "Descrição resumida PDF" in df.columns

    valores: List[float] = []
    mercados: List[str] = []
    fontes: List[str] = []

    # pré-cálculo: lista de descrições normalizadas do catálogo
    descs_norm = catalogo["_desc_norm"].tolist()

    for _, row in df.reset_index(drop=True).iterrows():
        melhor_preco = math.nan
        melhor_mercado = ""
        melhor_fonte = ""
        achou = False

        try:
            # 1️⃣ por código
            if tem_cod:
                cod = str(row.get("Código PDF", "")).strip()
                if cod:
                    sub = catalogo[catalogo["_codigo_norm"] == cod]
                    if not sub.empty:
                        preco = sub["preco"].mean(skipna=True)
                        if not math.isnan(preco):
                            melhor_preco = float(preco)
                            melhor_mercado = "; ".join(sub["mercado"].dropna().astype(str).unique().tolist())
                            melhor_fonte = "; ".join(sub["fonte"].dropna().astype(str).unique().tolist())
                            achou = True

            # 2️⃣ por similaridade (se não achou pelo código)
            if not achou and tem_desc:
                desc_norm = _norm_txt(str(row.get("Descrição resumida PDF", "")))
                if desc_norm:
                    # calcula similaridade uma vez por item
                    sims = [_token_set_overlap(d, desc_norm) for d in descs_norm]
                    catalogo["__sim"] = sims
                    sub = catalogo[catalogo["__sim"] >= float(min_score)]
                    if not sub.empty:
                        best = sub.sort_values("__sim", ascending=False).iloc[0]
                        preco = _to_float(best["preco"])
                        if not math.isnan(preco):
                            melhor_preco = float(preco)
                            melhor_mercado = str(best["mercado"])
                            melhor_fonte = str(best["fonte"])
                            achou = True

        except Exception as exc:
            notify_error("buscar_precos_item", exc=exc)

        valores.append(melhor_preco)
        mercados.append(melhor_mercado)
        fontes.append(melhor_fonte)

    # limpeza segura
    if "__sim" in catalogo.columns:
        with pd.option_context("mode.chained_assignment", None):
            catalogo.drop(columns=["__sim"], inplace=True, errors="ignore")

    return valores, mercados, fontes
