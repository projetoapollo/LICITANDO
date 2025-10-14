import statistics

# =====================================================
#  LÓGICA APPOLARI - PESQUISA DE PREÇOS AUTOMÁTICA
# =====================================================

def calcular_media_appolari(lista_precos, corte_percentual=70):
    """
    Aplica a lógica oficial Appolari para cálculo de preço médio.
    - Remove o menor preço.
    - Elimina valores abaixo de (corte_percentual)% do maior.
    - Calcula média dos restantes.
    """

    # Verificação básica
    if not lista_precos or len(lista_precos) < 2:
        return 0.0, []

    # 1️⃣ Ordena e remove o menor preço
    precos_ordenados = sorted(lista_precos, reverse=True)
    precos_filtrados = precos_ordenados[:-1]

    # 2️⃣ Determina o valor de corte com base no percentual
    maior_preco = max(precos_filtrados)
    limite_corte = maior_preco * (corte_percentual / 100)

    # 3️⃣ Mantém apenas os preços >= limite
    precos_restantes = [p for p in precos_filtrados if p >= limite_corte]

    # 4️⃣ Calcula a média se restarem preços
    if precos_restantes:
        media = statistics.mean(precos_restantes)
    else:
        media = 0.0

    return round(media, 2), precos_restantes


# =====================================================
#  TESTE LOCAL (opcional)
# =====================================================
if __name__ == "__main__":
    exemplo_precos = [100, 85, 60, 40, 30]
    for corte in [70, 60, 50]:
        media, usados = calcular_media_appolari(exemplo_precos, corte)
        print(f"\nCorte {corte}% -> Média = R$ {media} | Usados: {usados}")
