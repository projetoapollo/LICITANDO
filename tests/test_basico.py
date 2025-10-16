import importlib, os, pandas as pd

def test_assinatura_buscar_precos():
    mod = importlib.import_module("price_search")
    assert hasattr(mod, "buscar_precos")
    try:
        mod.buscar_precos(pd.DataFrame(), min_score=0.7)
    except TypeError as e:
        raise AssertionError(f"Assinatura errada: {e}")

def test_arquivos_existem():
    assert os.path.exists("data/catalogo_precos.csv"), "Falta data/catalogo_precos.csv"
    assert os.path.exists("static/logo_apolari.png"), "Falta static/logo_apolari.png"
