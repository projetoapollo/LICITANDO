import io
import pandas as pd
import time
from openpyxl import Workbook

# ==========================================
#  FUNÇÃO PRINCIPAL - PROCESSAMENTO DO PDF
# ==========================================

def processar_pdf(uploaded_file):
    """
    Simula a leitura e extração de dados de um PDF,
    aplica a lógica Appolari e devolve um Excel em memória.
    """

    time.sleep(2)  # pequeno atraso para simular OCR e IA

    # ------------------------------------------
    # Simulação de extração Appolari Turbo
    # ------------------------------------------
    dados = [
        {"Nº": 1, "Código PDF": "095.010.505", "Descrição resumida PDF": "BARRA DE ROSCA POLIDA MODELO NC 3/8", "Unidade": "METRO", "Valor médio do produto": 200.00, "Status": "✅", "Descrição localizada / Mercado": "Barra Roscada NC 3/8 Polida Vonder 1 Metro", "Fontes": "Mercado Livre"},
        {"Nº": 2, "Código PDF": "095.010.506", "Descrição resumida PDF": "ARRUELA LISA 3/8 ZINCADA", "Unidade": "UNIDADE", "Valor médio do produto": 0.35, "Status": "⚠️", "Descrição localizada / Mercado": "Arruela Lisa Zincada 3/8", "Fontes": "Leroy Merlin"},
        {"Nº": 3, "Código PDF": "095.010.507", "Descrição resumida PDF": "PORCA SEXTAVADA 3/8 ZINCADA", "Unidade": "UNIDADE", "Valor médio do produto": 0.40, "Status": "✅", "Descrição localizada / Mercado": "Porca Sextavada 3/8 Zincada", "Fontes": "ObraMax"},
    ]

    df = pd.DataFrame(dados)

    # ------------------------------------------
    # GERAÇÃO DO EXCEL EM MEMÓRIA
    # ------------------------------------------
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Cotacao_Final')
    output.seek(0)

    return output.getvalue()

# ==========================================
# TESTE LOCAL (opcional)
# ==========================================
if __name__ == "__main__":
    class DummyFile:
        name = "teste.pdf"
        def read(self):
            return b"simulacao"

    resultado = processar_pdf(DummyFile())
    print("Planilha gerada em memória com sucesso. Tamanho:", len(resultado))
