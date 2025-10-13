import streamlit as st
import pandas as pd
from datetime import datetime

# ===========================
# LICITANDO - Projeto Appolari
# ===========================

st.set_page_config(
    page_title="LICITANDO - Appolari",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 LICITANDO - Sistema Appolari")
st.markdown("---")

st.success("✅ Aplicação carregada com sucesso!")

st.write("""
Este é o **painel inicial do projeto LICITANDO**, desenvolvido por Appolari e Coop.
Aqui será possível futuramente:
- Carregar editais e planilhas de licitação,
- Fazer análise automática de preços,
- Gerar relatórios com IA e exportar para Excel.

Por enquanto, este é apenas o **painel base** configurado para rodar no Render.
""")

st.info("Dica: tudo o que aparecer aqui será visível publicamente em licitando.onrender.com")

# Exemplo de tabela simples
dados_exemplo = {
    "Item": ["Cimento", "Areia", "Brita"],
    "Unidade": ["Saco", "m³", "m³"],
    "Preço Base": [35.50, 120.00, 145.00],
    "Atualizado em": [datetime.now().strftime("%d/%m/%Y %H:%M:%S")]*3
}

df = pd.DataFrame(dados_exemplo)
st.dataframe(df)

st.markdown("---")
st.caption("🚀 Sistema hospedado com Streamlit + Render | Appolari © 2025")
