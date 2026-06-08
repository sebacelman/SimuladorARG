import streamlit as st
import numpy as np
import pandas as pd

st.set_page_config(page_title="UVA vs SPY", layout="wide")
st.title("⚖️ Simulación: Cancelar Crédito UVA vs Invertir en S&P 500")

# ==========================================
# 1. INPUTS DEL USUARIO
# ==========================================
st.sidebar.header("Datos del Crédito y Flujo")
flujo_mensual_usd = st.sidebar.number_input("Flujo Mensual Disponible (USD CCL)", value=2000)
saldo_uva = st.sidebar.number_input("Saldo de Deuda (UVAs)", value=47859)
cuotas_restantes = st.sidebar.number_input("Cuotas Restantes", value=83)
tna_credito = st.sidebar.number_input("Tasa Nominal Anual (%)", value=5.5, step=0.1) / 100

st.sidebar.header("Variables Macroeconómicas")
valor_uva_oficial = st.sidebar.number_input("Valor UVA en USD Oficial (Aprox)", value=1.15, step=0.05)
brecha_actual = st.sidebar.slider("Brecha Actual", 0.0, 1.5, 0.30, format="%.2f")

iteraciones = 1000
meses_simulacion = 120 # 10 años para ver el efecto post-cancelación
anio_inicio = 2026

# ==========================================
# 2. MOTOR MATEMÁTICO
# ==========================================
if st.sidebar.button("🚀 Simular 10 Años (Mes a Mes)", type="primary"):
    barra = st.progress(0)
    
    # Parámetros mensuales
    tasa_mensual_uva = tna_credito / 12
    
    # Fórmula de cuota constante (Sistema Francés en UVAs)
    cuota_uva_fija = saldo_uva * (tasa_mensual_uva * (1 + tasa_mensual_uva)**cuotas_restantes) / ((1 + tasa_mensual_uva)**cuotas_restantes - 1)
    
    # Parámetros SPY (Mensualizados)
    mu_spy_mensual = 0.07 / 12
    vol_spy_mensual = 0.15 / np.sqrt(12)
    
    # Matrices de resultados
    portafolio_A = np.zeros(iteraciones) # Pagar cuota e invertir resto
    portafolio_B = np.zeros(iteraciones) # Adelantar todo y luego invertir
    
    # Matriz para rastrear la deuda y el costo de la UVA
    deuda_A = np.full(iteraciones, float(saldo_uva))
    deuda_B = np.full(iteraciones, float(saldo_uva))
    rutas_costo_uva = np.zeros((iteraciones, meses_simulacion)) # NUEVA MATRIZ PARA EL GRÁFICO
    
    brecha_actual_arr = np.full(iteraciones, brecha_actual)
    velocidad_reversion_mensual = 0.1 
    
    for mes in range(1, meses_simulacion + 1):
        anio_actual = anio_inicio + (mes // 12)
        
        # --- 1. SIMULAR MACROECONOMÍA ---
        if anio_actual % 2 != 0:
            mu_brecha = 0.70 # Año Impar (Electoral)
            vol_brecha = 0.07 
        else:
            mu_brecha = 0.25 # Año Par
            vol_brecha = 0.03
            
        shock = np.random.normal(0, vol_brecha, iteraciones)
        cambio_brecha = velocidad_reversion_mensual * (mu_brecha - brecha_actual_arr) + shock
        brecha_actual_arr = np.maximum(0.0, brecha_actual_arr + cambio_brecha)
        
        # Costo de 1 UVA en dólares CCL este mes
        costo_uva_usd_ccl = valor_uva_oficial / (1 + brecha_actual_arr)
        
        # GUARDAMOS EL COSTO PARA EL GRÁFICO
        rutas_costo_uva[:, mes-1] = costo_uva_usd_ccl
        
        # Rendimiento del S&P 500 este mes
        retorno_spy = np.random.normal(mu_spy_mensual, vol_spy_mensual, iteraciones)
        
        # --- 2. ESCENARIO A: Cuota Normal + SPY ---
        portafolio_A = portafolio_A * (1 + retorno_spy)
        deben_A = (deuda_A > 0)
        costo_cuota_usd = cuota_uva_fija * costo_uva_usd_ccl
        inversion_disponible_A = np.where(deben_A, flujo_mensual_usd - costo_cuota_usd, flujo_mensual_usd)
        deuda_A = np.where(deben_A, deuda_A - (cuota_uva_fija - (deuda_A * tasa_mensual_uva)), 0)
        portafolio_A += inversion_disponible_A
        
        # --- 3. ESCENARIO B: Adelantar Capital a Muerte ---
        portafolio_B = portafolio_B * (1 + retorno_spy)
        deben_B = (deuda_B > 0)
        uvas_comprables = flujo_mensual_usd / costo_uva_usd_ccl
        interes_mes_B = deuda_B * tasa_mensual_uva
        amortizacion_B = uvas_comprables - interes_mes_B
        cancela_este_mes = deben_B & (amortizacion_B >= deuda_B)
        
        deuda_B = np.where(deben_B & ~cancela_este_mes, deuda_B - amortizacion_B, 0)
        uvas_sobrantes = np.where(cancela_este_mes, amortizacion_B - deuda_B, 0) 
        inversion_disponible_B = np.where(cancela_este_mes, uvas_sobrantes * costo_uva_usd_ccl, 0)
        inversion_disponible_B = np.where(~deben_B & ~cancela_este_mes, flujo_mensual_usd, inversion_disponible_B)
        portafolio_B += inversion_disponible_B
        
        barra.progress(mes / meses_simulacion)
        
    barra.empty()
    
    # ==========================================
    # 4. RESULTADOS (Mes 120 / Año 10)
    # ==========================================
    st.header(f"Patrimonio Neto tras 10 años")
    st.write("*(Asumiendo que aportás USD 2.000 mensuales incluso tras saldar la deuda)*")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Opción A: Pagar Cuota + Invertir")
        st.metric("Promedio Esperado", f"USD {np.mean(portafolio_A):,.0f}")
        st.write(f"Peor Escenario (P5): USD {np.percentile(portafolio_A, 5):,.0f}")
        
    with col2:
        st.subheader("Opción B: Adelantar Capital + Invertir")
        st.metric("Promedio Esperado", f"USD {np.mean(portafolio_B):,.0f}")
        st.write(f"Peor Escenario (P5): USD {np.percentile(portafolio_B, 5):,.0f}")
        
    diferencia = portafolio_A - portafolio_B
    probabilidad_A_gana = np.sum(diferencia > 0) / iteraciones * 100
    
    st.markdown("---")
    if np.mean(diferencia) > 0:
        st.success(f"🏆 **Conclusión del Modelo:** La Opción A (Invertir) te deja en promedio USD {np.mean(diferencia):,.0f} más. Gana en el {probabilidad_A_gana:.1f}% de los escenarios.")
    else:
        st.warning(f"🏆 **Conclusión del Modelo:** La Opción B (Adelantar) es superior, dejándote con USD {abs(np.mean(diferencia)):,.0f} extra en promedio. Gana en el {100-probabilidad_A_gana:.1f}% de los escenarios.")

    # ==========================================
    # 5. VISUALIZACIÓN DE LA UVA EN CCL
    # ==========================================
    st.markdown("---")
    st.subheader("📉 Evolución del Costo de 1 UVA en Dólares CCL")
    st.write("Muestra de 100 escenarios al azar a lo largo de los 120 meses. Observá cómo la ciclicidad electoral abarata la cuota en años impares.")
    
    # Tomamos 100 escenarios aleatorios de la matriz que creamos
    indices_muestra = np.random.choice(iteraciones, 100, replace=False)
    df_uva = pd.DataFrame(rutas_costo_uva[indices_muestra, :].T)
    
    # Renombramos el índice para que el eje X vaya del Mes 1 al 120
    df_uva.index = range(1, meses_simulacion + 1)
    
    st.line_chart(df_uva)
