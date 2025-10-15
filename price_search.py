# price_search.py
# -------------------------------------------------------------------
# Busca preços para os itens do DF do parser:
#  - Se o código existir no catálogo, usa apenas esses matches.
#  - Senão, calcula similaridade por descrição e aplica min_score.
# Retorna 3 listas com o mesmo comprimento de df:
#  [valores_medios], [mercados_concat], [fontes_concat]
# -------------------------------------------------------------------

from __future__ import annotations
import os
import unicodedata
import difflib
import pandas as pd
from typing import Tuple, List

# Caminho padrão do catálogo “manual”
CATALOGO_PATH = os.path.join("data", "catalogo_precos.csv")

def _normalize_txt(s: str) -> str:
    """Remove acentos, pontuação solta e normaliza espaços."""
    if not isinstance(s, str):
        return ""
    s = s.lower()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    # troca pontuações comuns por espaço e compacta
    for ch in [",", ";", ".", "–", "—", "-", "/", "\\", "(", ")", "[", "]"]:
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    return s

def _carregar_catalogo(caminho: str = CATALOGO_PATH) -> pd.DataFrame:
    """
    Carrega o catálogo CSV com colunas esperadas:
    descricao, unidade, preco, mercado, fonte, codigo (opcional)
    """
    if not os.path.exists(caminho):
        # catálogo ausente: devolve DF vazio com colunas padrão
        return pd.DataFrame(columns=["descricao","unidade","preco","mercado","fonte","codigo"])

    dfc = pd.read_csv(caminho, sep=",", encoding="utf-8", keep_default_na=False)
    # Garante colunas
    for col in ["descricao","unidade","preco","mercado","fonte","codigo"]:
        if col not in dfc.columns:
            dfc[col] = ""
    # Normalizações úteis
    dfc["__desc_norm"] = dfc["descricao"].apply(_normalize_txt)
    dfc["__codigo_norm"] = (
        dfc.get("codigo", "").astype(str)
        .str.replace(r"[.\s]", "", regex=True)
    )
    # preco numérico
    dfc["preco"] = pd.to_numeric(dfc["preco"], errors="coerce")
    return dfc

def _similaridade(a: str, b: str) -> float:
    """0..1 usando SequenceMatcher (rápido e sem dependências)."""
    return difflib.SequenceMatcher(None, a, b).ratio()

def buscar_precos(df: pd.DataFrame, min_score: float = 0.70) -> Tuple[List[float], List[str], List[str]]:
    """
    df: precisa ter colunas:
        'Código PDF', 'Descrição resumida PDF', 'Unidade' (opcional), 'Quantidade' (opcional)
    min_score: similaridade mínima (0..1) quando comparando por descrição.
    """
    cat = _carregar_catalogo()

    valores: List[float] = []
    mercados: List[str] = []
    fontes: List[str] = []

    if cat.empty:
        # Sem catálogo: devolve placeholders
        n = len(df)
        return [None]*n, [""]*n, [""]*n

    for _, row in df.iterrows():
        cod = str(row.get("Código PDF", "")).strip()
        cod_norm = "".join(ch for ch in cod if ch.isdigit())
        desc = str(row.get("Descrição resumida PDF", ""))
        desc_norm = _normalize_txt(desc)

        # 1) Tenta por código (exato no catálogo, desconsiderando pontos/espaços)
        subset = cat[cat["__codigo_norm"] == cod_norm] if cod_norm else pd.DataFrame()
        if subset.empty:
            # 2) Fallback: similaridade por descrição
            cat["__score"] = cat["__desc_norm"].apply(lambda t: _similaridade(desc_norm, t))
            subset = cat[cat["__score"] >= float(min_score)]

        if subset.empty or subset["preco"].dropna().empty:
            valores.append(None)
            mercados.append("")
            fontes.append("")
            continue

        # média de preços
        media = subset["preco"].dropna().mean()

        # concatena mercados e fontes (sem duplicar demais)
        mercados_join = ", ".join(subset["mercado"].astype(str).head(3).tolist())
        fontes_join = ", ".join(subset["fonte"].astype(str).head(3).tolist())

        valores.append(round(float(media), 2))
        mercados.append(mercados_join)
        fontes.append(fontes_join)

    return valores, mercados, fontes
    from observability import guard, AppError
import pandas as pd

@guard("buscar_precos")
def buscar_precos(df: "pd.DataFrame", *, similaridade_minima: float = 0.70):
    # Exemplo de validações:
    if "Descrição resumida PDF" not in df.columns:
        raise AppError("Coluna 'Descrição resumida PDF' ausente no DataFrame.",
                       code="COLUNA_FALTANDO",
                       hint="Confirme a etapa de extração/normalização.")
    if not (0.0 <= similaridade_minima <= 1.0):
        raise AppError("Parâmetro 'similaridade_minima' inválido.",
                       code="PARAM_INVALIDO",
                       hint="Use valor entre 0.0 e 1.0 (ex.: 0.7).")

    # ... Sua lógica atual de pesquisa (catálogo + fontes externas)
    # Deve retornar 3 listas/Series: valores_medios, mercados, fontes
    return valores_medios, mercados, fontes


