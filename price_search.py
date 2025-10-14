# price_search.py
# ----------------------------------------------------
# Busca/estima preços para os itens do DF do PDF.
#
# Como funciona:
# - (Opcional) Lê um catálogo local em data/catalogo_precos.csv
#   com as colunas: descricao, unidade, preco, mercado, fonte, [codigo]
# - Faz matching por similaridade de texto (0..1) + unidade/código,
#   aplica min_score, calcula média e agrega fontes/mercados.
#
# Assinatura:
#   buscar_precos(df: pd.DataFrame, min_score: float = 0.70)
#     -> (valores_medios: List[float|None],
#         mercados: List[str],
#         fontes:  List[str])
# ----------------------------------------------------

from __future__ import annotations
from typing import List, Tuple, Optional
import os
import math
import csv
import unicodedata
from difflib import SequenceMatcher
from statistics import fmean

import pandas as pd

# Caminho padrão do catálogo local
CATALOGO_PATH = os.path.join("data", "catalogo_precos.csv")

# Nomes de colunas esperadas no DF de entrada
COL_DESC = "Descrição resumida PDF"
COL_UNID = "Unidade"
COL_COD  = "Código PDF"

def _strip_accents(s: str) -> str:
    """Remove acentos para facilitar o matching."""
    try:
        return "".join(
            ch for ch in unicodedata.normalize("NFKD", s)
            if not unicodedata.combining(ch)
        )
    except Exception:
        return s

def _norm_text(s: Optional[str]) -> str:
    if s is None:
        return ""
    s2 = _strip_accents(str(s)).lower().strip()
    # simplificações leves
    return " ".join(s2.split())

def _similaridade(a: str, b: str) -> float:
    """0..1 — usa SequenceMatcher (rápido e sem deps externas)."""
    a2, b2 = _norm_text(a), _norm_text(b)
    if not a2 or not b2:
        return 0.0
    return SequenceMatcher(None, a2, b2).ratio()

def _carregar_catalogo(path: str = CATALOGO_PATH) -> List[dict]:
    """Carrega o CSV de catálogo se existir. Caso contrário, lista vazia."""
    if not os.path.exists(path):
        return []
    out: List[dict] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # normaliza campos conhecidos
            row_norm = {
                "descricao": row.get("descricao", ""),
                "unidade":   row.get("unidade", ""),
                "preco":     row.get("preco", ""),
                "mercado":   row.get("mercado", ""),
                "fonte":     row.get("fonte", ""),
                "codigo":    row.get("codigo", ""),  # opcional
            }
            # tenta converter preco
            preco_raw = str(row_norm["preco"]).strip().replace(".", "").replace(",", ".")
            try:
                row_norm["preco"] = float(preco_raw)
            except Exception:
                row_norm["preco"] = None
            out.append(row_norm)
    return out

def _match_item(
    desc_item: str,
    unid_item: str,
    cod_item: str,
    catalogo: List[dict],
    min_score: float
) -> Tuple[Optional[float], str, str]:
    """
    Retorna (preco_medio, mercados_concat, fontes_concat) para um item.
    - Tenta match forte por código (se existir em ambos).
    - Caso não, usa similaridade na descrição, filtrando por unidade (se houver).
    """
    if not catalogo:
        return None, "", ""

    desc_item_n = _norm_text(desc_item)
    unid_item_n = _norm_text(unid_item)
    cod_item_n  = _norm_text(cod_item)

    candidatos: List[Tuple[float, dict]] = []

    # 1) Se temos código, tenta match exato de código (mais forte)
    if cod_item_n:
        for row in catalogo:
            cod_cat = _norm_text(row.get("codigo", ""))
            if cod_cat and cod_cat == cod_item_n and row.get("preco") is not None:
                candidatos.append((1.0, row))  # score 1.0 por código idêntico

    # 2) Caso não haja por código suficiente, usa descrição
    if not candidatos:
        for row in catalogo:
            desc_cat = row.get("descricao", "")
            unid_cat = row.get("unidade", "")
            preco    = row.get("preco", None)

            if preco is None:
                continue

            # Se a unidade está preenchida no item, preferimos bater unidade
            if unid_item_n and _norm_text(unid_cat) and _norm_text(unid_cat) != unid_item_n:
                continue  # unidades diferentes, pula

            score = _similaridade(desc_item, desc_cat)
            if score >= min_score:
                candidatos.append((score, row))

    if not candidatos:
        return None, "", ""

    # Ordena por maior score
    candidatos.sort(key=lambda x: x[0], reverse=True)

    # Podemos pegar os top-K; aqui, pego todos >= min_score (ou todos por código)
    precos = [c[1]["preco"] for c in candidatos if c[1].get("preco") is not None]
    if not precos:
        return None, "", ""

    # Média robusta (fmean é rápido; se quiser, dá pra filtrar outliers depois)
    preco_medio = float(fmean(precos))

    # Agrega mercados e fontes únicos (mantendo ordem de aparição)
    def _uniq_keep(seq: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for s in seq:
            s2 = (s or "").strip()
            if not s2:
                continue
            if s2 not in seen:
                seen.add(s2)
                out.append(s2)
        return out

    mercados = _uniq_keep([c[1].get("mercado", "") for c in candidatos])
    fontes   = _uniq_keep([c[1].get("fonte", "")   for c in candidatos])

    mercados_s = "; ".join(mercados)[:500]  # evita campos enormes
    fontes_s   = "; ".join(fontes)[:500]

    return preco_medio, mercados_s, fontes_s

def buscar_precos(df: pd.DataFrame, min_score: float = 0.70) -> Tuple[List[Optional[float]], List[str], List[str]]:
    """
    Recebe o DataFrame base (itens do PDF) e retorna:
      - valores_medios: lista de floats (ou None) por item
      - mercados:       descrição de onde foi encontrado (string)
      - fontes:         lista/concat de sites (string)

    Observações:
    - Se não houver catálogo local, retorna None/"" sem quebrar o app.
    - min_score controla o corte de similaridade para os matches por DESCRIÇÃO.
      (Se houver match por CÓDIGO, usa score 1.0)
    """
    n = len(df)
    valores_medios: List[Optional[float]] = [None] * n
    mercados: List[str] = [""] * n
    fontes:  List[str] = [""] * n

    catalogo = _carregar_catalogo(CATALOGO_PATH)

    # Itera sobre o DF de entrada
    for i, row in df.iterrows():
        desc = str(row.get(COL_DESC, "") or "").strip()
        unid = str(row.get(COL_UNID, "") or "").strip()
        cod  = str(row.get(COL_COD,  "") or "").strip()

        preco, merc, font = _match_item(desc, unid, cod, catalogo, min_score=min_score)
        # Guarda resultados
        valores_medios[i] = float(preco) if (preco is not None and not math.isnan(preco)) else None
        mercados[i] = merc
        fontes[i] = font

    return valores_medios, mercados, fontes
