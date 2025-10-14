import streamlit as st
import os

# =======================================
# CONFIGURAÇÕES INICIAIS
# =======================================
st.set_page_config(page_title="Appolari Turbo IA", layout="centered", page_icon="⚙️")

st.title("🧠 Sistema Appolari Turbo V3.2")
st.success("Aplicação carregada com sucesso! 🚀")

# Tentativa segura de importar o script principal
try:
    from script_principal_turbo import processar_pdf
    processamento_disponivel = True
except Exception as e:
    processamento_disponivel = False
    st.warning("⚠️ Módulo principal não encontrado no servidor Render.")
    st.text(f"Detalhe técnico: {e}")

# =======================================
# INTERFACE PRINCIPAL
# =======================================
uploaded_file = st.file_uploader("📤 Envie o PDF de cotação", type=["pdf"])

if uploaded_file is not None:
    st.success("✅ PDF carregado com sucesso!")

    if processamento_disponivel:
        if st.button("▶️ Rodar Sistema Appolari"):
            try:
                st.info("⏳ Processando... aguarde alguns instantes...")
                df, output_excel = processar_pdf(uploaded_file)
                st.success("✅ Processamento concluído com sucesso!")
                st.download_button("📥 Baixar planilha gerada", data=output_excel, file_name="cotacao_final.xlsx")
            except Exception as e:
                st.error(f"❌ Erro ao processar: {e}")
    else:
        st.error("🚫 O módulo 'script_principal_turbo.py' não pôde ser carregado nesta instância Render.")
else:
    st.info("📄 Envie um arquivo PDF para começar.")

# Rodapé
st.divider()
st.caption("Desenvolvido por Pai Appolari e Filho Coop 💚")
