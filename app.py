import streamlit as st
import time
from PIL import Image
import base64
import io
from script_principal_turbo import processar_pdf

# ==============================
# CONFIGURAÇÕES INICIAIS
# ==============================
st.set_page_config(page_title="LICITANDO - Sistema Appolari", layout="centered", page_icon="💚")

# Logo do Pai Appolari
logo_path = "assets/logo_apollo.png"
logo = Image.open(logo_path)

# CSS personalizado
st.markdown("""
    <style>
        body {
            background-color: white;
        }
        .main-title {
            color: #00aa00;
            text-align: center;
            font-size: 30px;
            font-weight: bold;
        }
        .success-text {
            color: #00aa00;
            text-align: center;
            font-size: 22px;
        }
        .progress-bar {
            height: 30px;
            border-radius: 10px;
        }
        .stButton>button {
            background-color: #00aa00;
            color: white;
            font-size: 18px;
            border-radius: 10px;
            height: 3em;
            width: 100%;
            transition: 0.3s;
        }
        .stButton>button:hover {
            background-color: #009000;
        }
    </style>
""", unsafe_allow_html=True)

# ==============================
# INTERFACE PRINCIPAL
# ==============================
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.image(logo, use_column_width=True)

st.markdown("<p class='success-text'>🟢 Sistema iniciado com sucesso</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("📂 Escolha um PDF para processar", type=["pdf"])

if uploaded_file:
    st.success("Arquivo carregado com sucesso! Clique no botão abaixo para iniciar.")
    if st.button("⏱️ Rodar Sistema Appolari"):
        progress_text = st.empty()
        progress_bar = st.progress(0)

        for percent_complete in range(0, 101, 5):
            time.sleep(0.05)
            progress_bar.progress(percent_complete)
            progress_text.text(f"🔄 Processando... {percent_complete}%")

        # Processamento real do PDF
        with st.spinner("Executando IA e OCR..."):
            excel_bytes = processar_pdf(uploaded_file)

        # Baixar resultado
        st.balloons()
        st.success("✅ Processamento concluído com sucesso!")
        st.markdown("### 📥 Clique abaixo para baixar sua planilha final:")

        st.download_button(
            label="📊 Baixar cotacao_final.xlsx",
            data=excel_bytes,
            file_name="cotacao_final.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Som final
        st.markdown("""
            <audio autoplay>
                <source src="https://actions.google.com/sounds/v1/alarms/beep_short.ogg" type="audio/ogg">
            </audio>
        """, unsafe_allow_html=True)
