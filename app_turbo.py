# app_turbo.py
import os
import sys
import streamlit as st
import pandas as pd

# 1) Configuração inicial
st.set_page_config(page_title="Appolari Turbo IA", layout="centered", page_icon="🧠")

# 2) Cabeçalho e diagnóstico rápido (pode remover depois)
st.title("🧠 Sistema Appolari Turbo V3.2")
st.success("Aplicação carregada com sucesso! ✅")

st.write("APP iniciou ✅")
st.write(f"Python: {sys.version.split()[0]}")
st.code(
    {
        k: os.environ[k]
        for k in ("PYTHONUNBUFFERED", "STREAMLIT_SERVER_HEADLESS")
        if k in os.environ
    },
    language="json",
)

# 3) Import do módulo de parsing
processamento_disponivel = False
processar_pdf = None
try:
    from script_principal_turbo import processar_pdf  # nosso parser
    processamento_disponivel = True
except Exception as e:
    st.warning("⚠️ Módulo principal não encontrado no servidor Render.")
    with st.expander("Detalhe técnico (para depuração):"):
        st.code(repr(e), language="python")

st.divider()

# 4) Interface principal
uploaded_file = st.file_uploader("📄 Envie o PDF de cotação", type=["pdf"])
if uploaded_file is not None:
    st.success("✅ PDF carregado com sucesso!")

    if processamento_disponivel:
        if st.button("▶️ Rodar Sistema Appolari"):
            with st.spinner("🔎 Processando... aguarde alguns instantes..."):
                try:
                    df, output_excel = processar_pdf(uploaded_file)
                    st.success("🎉 Processamento concluído com sucesso!")
                    st.dataframe(df, use_container_width=True)

                    st.download_button(
                        "⬇️ Baixar planilha gerada",
                        data=output_excel,
                        file_name="cotacao_final.xlsx",
                        mime=(
                            "application/vnd.openxmlformats-officedocument."
                            "spreadsheetml.sheet"
                        ),
                    )
                except Exception as e:
                    st.error("❌ Erro ao processar o PDF.")
                    with st.expander("Ver detalhes do erro"):
                        st.exception(e)
    else:
        st.error(
            "❌ O módulo `script_principal_turbo.py` não pôde ser carregado nesta instância."
        )
else:
    st.info("📥 Envie um arquivo PDF para começar.")

# 5) Rodapé
st.divider()
st.caption("Desenvolvido por Pai Appolari e Filho Coop 💚")
