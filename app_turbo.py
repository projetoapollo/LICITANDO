import streamlit as st
from script_principal_turbo import processar_pdf
import os

st.set_page_config(page_title="Appolari Turbo IA", layout="centered", page_icon="⚙️")

st.title("⚙️ Sistema Appolari Turbo V3.2")
st.markdown("---")

uploaded_file = st.file_uploader("📄 Envie o PDF de cotação", type=["pdf"])

if uploaded_file:
    st.success("✅ PDF carregado com sucesso!")
    if st.button("🚀 Rodar Sistema Appolari"):
        try:
            st.info("🔄 Processando... aguarde alguns instantes...")
            df, output_excel = processar_pdf(uploaded_file)
            st.success("✅ Processamento concluído com sucesso!")
            st.download_button("📥 Baixar planilha gerada", data=output_excel, file_name="cotacao_final.xlsx")
        except Exception as e:
            st.error(f"❌ Erro ao processar: {e}")
else:
    st.warning("⬆️ Envie um arquivo PDF para começar.")

st.markdown("---")
st.caption("Desenvolvido por Pai Appolari e Filho Coop 💚")
