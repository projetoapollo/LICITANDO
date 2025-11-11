# price_search.py
from __future__ import annotations

import math
import os
import re
from typing import List, Tuple, Optional, Any, Callable

import pandas as pd

# observabilidade opcional (guard + notify_error com fallback seguro)
try:
    from observability import guard, notify_error  # type: ignore
except Exception:
    def guard(_name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def _decor(fn: Callable[..., Any]) -> Callable[..., Any]:
            return fn
        return _decor

    def notify_error(_step: str, exc: BaseException | None = None, **_kw: Any) -> None:
        return None

CATALOGO_ARQ = "data/catalogo_precos.csv"

# Helpers de normalização/semelhança
_SPACES = re.compile(r"\s+")
_PUNCTS = re.compile(r"[^\w\s]", flags=re.UNICODE)

def _log(msg: str) -> None:
    # aparece nos Logs do Render
    print(f"[PRICE] {msg}")

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
    try:
        return float(str(x).replace(",", "."))
    except Exception:
        return math.nan

def _read_csv_smart(path: str) -> tuple[pd.DataFrame, str, str | None]:
    """Tenta ler CSV com várias combinações de encoding e separador."""
    attempts = [
        ("utf-8", None), ("utf-8-sig", None), ("latin-1", None),
        ("utf-8", ";"), ("utf-8-sig", ";"), ("latin-1", ";"),
        ("utf-8", ","), ("utf-8-sig", ","), ("latin-1", ","),
    ]
    for enc, sep in attempts:
        try:
            df = pd.read_csv(path, encoding=enc, sep=sep, engine="python")
            if df.shape[1] >= 2:
                return df, enc, sep
        except Exception:
            continue
    return pd.DataFrame(), "unknown", None

def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Mapeia colunas do catálogo para o padrão esperado."""
    if df.empty:
        return df

    # normaliza nomes
    norm_cols = {c: _norm_txt(c) for c in df.columns}
    # candidatos
    desc_alias = {"descricao", "descrição", "descricao do produto", "descrição do produto",
                  "produto", "item", "nome", "nome do produto", "nome do material"}
    unid_alias = {"un", "unid", "unidade", "und"}
    preco_alias = {"preco", "preço", "valor", "valor medio", "preco medio", "valor unit", "valor unitario"}
    mercado_alias = {"mercado", "cidade", "local", "regiao"}
    fonte_alias = {"fonte", "site", "url", "origem"}
    codigo_alias = {"codigo", "código", "cod", "cod item", "codigo item"}

    def pick(alias: set[str]) -> Optional[str]:
        for col, n in norm_cols.items():
            if n in alias:
                return col
        # tentativa por contains
        for col, n in norm_cols.items():
            for a in alias:
                if a in n:
                    return col
        return None

    mapping: dict[str, str] = {}
    c_desc = pick(desc_alias)
    c_unid = pick(unid_alias)
    c_preco = pick(preco_alias)
    c_merc = pick(mercado_alias)
    c_fonte = pick(fonte_alias)
    c_cod = pick(codigo_alias)

    if c_desc: mapping[c_desc] = "descricao"
    if c_unid: mapping[c_unid] = "unidade"
    if c_preco: mapping[c_preco] = "preco"
    if c_merc: mapping[c_merc] = "mercado"
    if c_fonte: mapping[c_fonte] = "fonte"
    if c_cod: mapping[c_cod] = "codigo"

    if mapping:
        df = df.rename(columns=mapping)

    # garante colunas
    for col in ["descricao", "unidade", "preco", "mercado", "fonte", "codigo"]:
        if col not in df.columns:
            df[col] = ""

    return df

def _carregar_catalogo(path: str = CATALOGO_ARQ) -> pd.DataFrame:
    """
    Lê o catálogo local. Espera colunas: descricao, unidade, preco, mercado, fonte, codigo
    mas tenta mapear automaticamente sinônimos e detecta ;/,, e encodings.
    """
    if not os.path.exists(path):
        _log(f"Catálogo não encontrado em '{path}'.")
        return pd.DataFrame(columns=["descricao", "unidade", "preco", "mercado", "fonte", "codigo"])

    raw, enc, sep = _read_csv_smart(path)
    _log(f"Catálogo lido: shape={raw.shape}, encoding={enc}, sep={'auto' if sep is None else repr(sep)}")
    if raw.empty:
        return pd.DataFrame(columns=["descricao", "unidade", "preco", "mercado", "fonte", "codigo"])

    df = _rename_columns(raw)

    # tipos / limpeza
    df["descricao"] = df["descricao"].astype(str)
    df["unidade"] = df["unidade"].astype(str)
    df["mercado"] = df["mercado"].astype(str)
    df["fonte"] = df["fonte"].astype(str)
    df["codigo"] = df["codigo"].astype(str).str.strip()
    df["preco"] = df["preco"].map(_to_float)

    # colunas auxiliares
    df["_desc_norm"] = df["descricao"].map(_norm_txt)
    df["_codigo_norm"] = df["codigo"].str.strip()

    # remove linhas sem descrição e sem código
    df = df[(df["_desc_norm"] != "") | (df["_codigo_norm"] != "")]
    _log(f"Catálogo normalizado: linhas úteis={len(df)}.")
    return df

def _pick_df_col(df: pd.DataFrame, prefer: list[str], fallback_contains: list[str]) -> Optional[str]:
    """Escolhe coluna no DF do PDF pelos nomes (case-insensitive)."""
    lowmap = {c: c.lower() for c in df.columns}
    for name in prefer:
        for c, l in lowmap.items():
            if l == name.lower():
                return c
    for frag in fallback_contains:
        for c, l in lowmap.items():
            if frag.lower() in l:
                return c
    return None

@guard("buscar_precos")
def buscar_precos(
    df: pd.DataFrame,
    min_score: float = 0.7,
    *,
    similaridade_minima: Optional[float] = None,  # alias opcional
) -> Tuple[List[float], List[str], List[str]]:
    """
    Retorna 3 listas (mesma ordem do DF):
      - valores (média/preço encontrado por item)
      - mercados (descrição/localidade)
      - fontes (URL/nome da fonte)
    """
    try:
        if similaridade_minima is not None:
            min_score = float(similaridade_minima)

        if df is None or df.empty:
            n = 0 if df is None else len(df)
            _log(f"DF de itens vazio (n={n}).")
            return [math.nan] * n, [""] * n, [""] * n

        catalogo = _carregar_catalogo(CATALOGO_ARQ)
        n = len(df)
        valores: List[float] = [math.nan] * n
        mercados: List[str] = [""] * n
        fontes: List[str] = [""] * n

        if catalogo.empty:
            _log("Catálogo vazio após leitura — verifique caminho/CSV.")
            return valores, mercados, fontes

        # Descobre colunas no DF
        cod_col = _pick_df_col(
            df,
            prefer=["Código PDF", "codigo pdf"],
            fallback_contains=["código", "codigo", "cod"]
        )
        desc_col = _pick_df_col(
            df,
            prefer=["Descrição resumida PDF", "descrição resumida pdf"],
            fallback_contains=["descrição", "descricao", "produto", "item", "material"]
        )

        _log(f"Colunas detectadas no DF: codigo={cod_col!r}, descricao={desc_col!r}, min_score={min_score:.2f}")

        for idx, row in df.reset_index(drop=True).iterrows():
            melhor_preco = math.nan
            melhor_mercado = ""
            melhor_fonte = ""
            achou = False

            # 1) por código
            if cod_col:
                cod = str(row.get(cod_col, "")).strip()
                if cod:
                    sub = catalogo[catalogo["_codigo_norm"] == cod]
                    if not sub.empty:
                        preco = sub["preco"].mean(skipna=True)
                        if not math.isnan(preco):
                            melhor_preco = float(preco)
                            melhor_mercado = "; ".join(sub["mercado"].dropna().astype(str).unique().tolist())
                            melhor_fonte = "; ".join(sub["fonte"].dropna().astype(str).unique().tolist())
                            achou = True

            # 2) por similaridade de descrição
            if not achou and desc_col:
                desc_norm = _norm_txt(str(row.get(desc_col, "")))
                if desc_norm:
                    catalogo["__sim"] = catalogo["_desc_norm"].map(lambda d: _token_set_overlap(d, desc_norm))
                    sub = catalogo[catalogo["__sim"] >= float(min_score)]
                    if not sub.empty:
                        best = sub.sort_values("__sim", ascending=False).iloc[0]
                        preco = _to_float(best["preco"])
                        if not math.isnan(preco):
                            melhor_preco = float(preco)
                            melhor_mercado = str(best["mercado"])
                            melhor_fonte = str(best["fonte"])
                            achou = True

            valores[idx] = melhor_preco
            mercados[idx] = melhor_mercado
            fontes[idx] = melhor_fonte

        if "__sim" in catalogo.columns:
            catalogo.drop(columns=["__sim"], inplace=True)

        # estatística final
        encontrados = sum(0 if math.isnan(v) else 1 for v in valores)
        _log(f"Busca concluída: {encontrados}/{n} itens com preço.")
        return valores, mercados, fontes

    except Exception as exc:
        notify_error("buscar_precos", exc=exc)
        _log(f"Erro em buscar_precos: {exc}")
        # fallback seguro
        n = 0 if df is None else len(df)
        return [math.nan] * n, [""] * n, [""] * n
