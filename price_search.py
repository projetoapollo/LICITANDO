# price_search.py
from __future__ import annotations

import os
import math
import re
from typing import List, Tuple

import pandas as pd

# ---------------------------------------------------------
# Tentativa de importar o decorator de observabilidade
# (se não existir, criamos um no-op para não quebrar)
# ---------------------------------------------------------
try:
    from observability import guard  # opcional
except Exception:
    def guard(_name: str):
        def _decorator(fn):
            return fn
        return _decorator


CATALOGO_PATH = "data/catalogo_precos.csv"

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
_SPACES = re.compile(r"\s+")
_PUNCTS = re.compile(r"[^\w\s]", flags=re.UNICODE)

def _norm_txt(txt: str) -> str:
    if not isinstance(txt, str):
        return ""
    txt = txt.lower()
    txt = _PUNCTS.sub(" ", txt)
    txt = _SPACES.sub(" ", txt).strip()
    return txt

def _token_set_overlap(a: str, b: str) -> float:
    """
    Similaridade simples por interseção de tokens.
    Retorna 0..1.
    """
    if not a or not b:
        return 0.0
    sa = set(_norm_txt(a).split())
    sb = set(_norm_txt(b).split())
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    uni = len(sa | sb)
    return inter / uni if uni else 0.0


def _carregar_catalogo(path: str = CATALOGO_PATH) -> pd.DataFrame:
    """
    Lê o catálogo de preços local (CSV).
    Espera colunas:
      descricao, unidade, preco, mercado, fonte, codigo
    Qualquer ausência é tratada com preenchimento vazio.
    """
    if not os.path.exists(path):
        # catálogo vazio
        return pd.DataFrame(
            columns=["descricao", "unidade", "preco", "mercado", "fonte", "codigo"]
        )

    df = pd.read_csv(path, encoding="utf-8")
    # Garante colunas
    for col in ["descricao", "unidade", "preco", "mercado", "fonte", "codigo"]:
        if col not in df.columns:
            df[col] = ""

    # Normaliza tipos
    df["descricao"] = df["descricao"].astype(str)
    df["unidade"] = df["unidade"].astype(str)
    df["mercado"] = df["mercado"].astype(str)
    df["fonte"] = df["fonte"].astype(str)
    df["codigo"] = df["codigo"].astype(str)
    # preço numérico
    def _to_float(x):
        try:
            return float(str(x).replace(",", "."))
        except Exception:
            return math.nan
    df["preco"] = df["preco"].map(_to_float)

    return df


# ---------------------------------------------------------
# Função principal
# ---------------------------------------------------------
@guard("buscar_precos")
def buscar_precos(
    df_itens: pd.DataFrame,
    similaridade_minima: float = 0.70,
) -> Tuple[List[float], List[str], List[str]]:
    """
    Recebe o DF base (já extraído do PDF) e retorna 3 listas:
      - valores_medios
      - mercados (descrição/localidade)
      - fontes  (URL ou nome da fonte)

    Regras de matching:
      1) Se houver coluna 'Código PDF', tenta casar por código (catalogo.codigo).
      2) Caso contrário, ou não encontre por código, casa por similaridade
         de tokens entre 'Descrição resumida PDF' e 'catalogo.descricao'
         (limiar = similaridade_minima, 0..1).
      3) Se não achar nada, retorna NaN / vazio.

    Observação: esta é uma heurística simples para rodar bem no Render Free.
    """
    catalogo = _carregar_catalogo(CATALOGO_PATH)

    n = len(df_itens)
    valores: List[float] = [math.nan] * n
    mercados: List[str] = [""] * n
    fontes: List[str] = [""] * n

    if catalogo.empty or df_itens is None or df_itens.empty:
        return valores, mercados, fontes

    # Acelera com colunas normalizadas
    catalogo["_desc_norm"] = catalogo["descricao"].map(_norm_txt)
    catalogo["_codigo_norm"] = catalogo["codigo"].astype(str).str.strip()

    tem_codigo = "Código PDF" in df_itens.columns
    tem_desc = "Descrição resumida PDF" in df_itens.columns

    for idx, row in df_itens.reset_index(drop=True).iterrows():
        melhor_preco = math.nan
        melhor_mercado = ""
        melhor_fonte = ""

        achou = False

        # 1) tentativa por código
        if tem_codigo:
            cod = str(row["Código PDF"]).strip()
            if cod:
                subset = catalogo[catalogo["_codigo_norm"] == cod]
                if not subset.empty:
                    # pegue a primeira linha (ou média)
                    # aqui, vamos de média dos preços daquele código
                    preco = subset["preco"].mean(skipna=True)
                    if not math.isnan(preco):
                        melhor_preco = float(preco)
                        # agrega mercados/fontes de todos encontrados
                        melhor_mercado = "; ".join(
                            subset["mercado"].dropna().astype(str).unique().tolist()
                        )
                        melhor_fonte = "; ".join(
                            subset["fonte"].dropna().astype(str).unique().tolist()
                        )
                        achou = True

        # 2) tentativa por similaridade de descrição
        if not achou and tem_desc:
            desc = str(row["Descrição resumida PDF"])
            desc_norm = _norm_txt(desc)
            if desc_norm:
                # computa similaridade e filtra
                catalogo["__sim"] = catalogo["_desc_norm"].map(
                    lambda d: _token_set_overlap(d, desc_norm)
                )
                subset = catalogo[catalogo["__sim"] >= float(similaridade_minima)]
                if not subset.empty:
                    # escolhe o melhor por maior similaridade
                    best = subset.sort_values("__sim", ascending=False).head(1)
                    preco = best["preco"].iloc[0]
                    if not math.isnan(preco):
                        melhor_preco = float(preco)
                        melhor_mercado = str(best["mercado"].iloc[0])
                        melhor_fonte = str(best["fonte"].iloc[0])
                        achou = True

        # Preenche resultados deste item
        valores[idx] = melhor_preco
        mercados[idx] = melhor_mercado
        fontes[idx] = melhor_fonte

    # Remove coluna temporária se tiver sido criada
    if "__sim" in catalogo.columns:
        catalogo.drop(columns=["__sim"], inplace=True)

    return valores, mercados, fontes
    # price_search.py
import pandas as pd

def buscar_precos(df: pd.DataFrame, similaridade_minima: float = 0.7):
    """
    Recebe o DF base (itens do PDF) e retorna 3 listas, na mesma ordem do DF:
      - valores_medios: list[float|None]
      - mercados:       list[str] (descrição/localidade)
      - fontes:         list[str] (links ou nomes de lojas)
    Pode consultar 'data/catalogo_precos.csv' como fallback simples.
    """
    # --- Exemplo mínimo com catálogo local ---
    import csv, os

    catalogo = []
    path_cat = os.path.join("data", "catalogo_precos.csv")
    if os.path.exists(path_cat):
        with open(path_cat, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                catalogo.append(row)

    valores, mercados, fontes = [], [], []
    for _, row in df.iterrows():
        desc = str(row.get("Descrição resumida PDF", "")).upper()
        unidade = str(row.get("Unidade", "")).upper()

        # matching tosco por substring no catálogo (apenas exemplo)
        candidatos = []
 
for c in catalogo:
    cdesc = str(c.get("descricao","")).upper()
    cunid = str(c.get("unidade","")).upper()
    if cdesc and cdesc in desc and (not unidade or cunid == unidade):
        try:
            preco = float(str(c.get("preco", "0")).replace(",", "."))
        except (TypeError, ValueError, AttributeError):
            preco = None

        candidatos.append((
            preco,
            c.get("mercado", ""),
            c.get("fonte", ""),
        ))         

       if candidatos:
    # preços válidos
    precos_validos = [p for (p, _m, _f) in candidatos if isinstance(p, (int, float))]
    media = round(sum(precos_validos) / len(precos_validos), 2) if precos_validos else None

    # juntar mercados/fontes (únicos)
    mercados_join = " | ".join(sorted({m for (_p, m, _f) in candidatos if m}))
    fontes_join = " | ".join(sorted({f for (_p, _m, f) in candidatos if f}))
else:
    media = None
    mercados_join = ""
    fontes_join = ""

# acrescentar resultados (fora do if/else)
valores.append(media)
mercados.append(mercados_join)
fontes.append(fontes_join)

return valores, mercados, fontes








