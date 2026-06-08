import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(page_title="UVA vs SPY", layout="wide")
st.title("⚖️ Simulación: Cancelar Crédito UVA vs Invertir en S&P 500")

# ==========================================
# 2. EXTRACCIÓN AUTOMÁTICA DE DATOS
# ==========================================
@st.cache_data(ttl=3600) 
def obtener_datos_macro():
    try:
        # 1. Extraemos SPY
        spy = yf.Ticker("SPY")
        per_actual = spy.info.get('trailingPE', 24.0)
        
        # 2. Extraemos Dólar Oficial desde Yahoo Finance
        usd_ars = yf.Ticker("USDARS=X").history(period="1d")
        oficial = float(usd_ars['Close'].iloc[-1])
        
        # 3. Calculamos el CCL real usando el ADR de Grupo Galicia (Ratio 10:1)
        ggal_ars = yf.Ticker("GGAL.BA").history(period="1d")
        ggal_usd = yf.Ticker("GGAL").history(period="1d")
        
        precio_ggal_ars = float(ggal_ars['Close'].iloc[-1])
        precio_ggal_usd = float(ggal_usd['Close'].iloc[-1])
        
        ccl_calculado = (precio_ggal_ars * 10) / precio_ggal_usd
        brecha_calculada = (ccl_calculado / oficial) - 1
        
        return per_actual, oficial, ccl_calculado, brecha_calculada, True
    except Exception as e:
        # Valores de respaldo por si falla la conexión a Yahoo
        return 24.0, 1000.0, 1350.0, 0.35, False

per_spy, valor_oficial, valor_ccl, brecha_calculada, api_ok = obtener_datos_macro()

# ==========================================
# 3. INPUTS DEL USUARIO
# ==========================================
st.sidebar.header("Datos del Crédito y Flujo")
flujo_mensual_usd = st.sidebar.number_input("Flujo Mensual Disponible (USD CCL)", value=2000)
saldo_uva = st.sidebar.number_input("Saldo de Deuda (UVAs)", value=47859)
cuotas_restantes = st.sidebar.number_input("Cuotas Restantes", value=83)
tna_credito = st.sidebar.number_input("Tasa Nominal Anual (%)", value=5.5, step=0.1) / 100

st.sidebar.header("Variables Macroeconómicas")
valor_uva_pesos = st.sidebar.number_input("Valor de 1 UVA hoy (ARS)", value=1200.0)
brecha_inicial_usuario = st.sidebar.slider("Brecha Actual (CCL vs Oficial)", 0.0, 1.5, brecha_calculada, format="%.2f")

st.sidebar.header("Motor Estadístico")
distribucion = st.sidebar.selectbox(
    "Distribución del S&P 500", 
    ["Normal (Clásica)", "T-Student (Colas Pesadas)"]
)

iteraciones = 1000
meses_simulacion = 120 
anio_inicio = 2026

# ==========================================
# 4. TABLERO DE CONTROL (Transparencia)
# ==========================================
if not api_ok:
    st.error("⚠️ Error de conexión. Usando datos de simulación temporales.")

st.markdown("### 🔍 Datos Base del Modelo")
colA, colB, colC, colD = st.columns(4)

valor_uva_usd_oficial = valor_uva_pesos / valor_oficial

colA.metric("Dólar Oficial (Yahoo)", f"ARS {valor_oficial:,.2f}")
colB.metric("Dólar CCL (Vía ADR GGAL)", f"ARS {valor_ccl:,.2f}")
colC.metric("Brecha Usada en Simulación", f"{brecha_inicial_usuario*100:.1f}%")
colD.metric("Costo 1 UVA (USD Oficial)", f"USD {valor_uva_usd_oficial:.2f}")

crecimiento_real_g = 0.02
inflacion_usd_i = 0.03
mu_spy_anual = (1 / per_spy) + crecimiento_real_g + inflacion_usd_i

st.info(f"**Valuación del S&P 500:** PER actual = **{per_spy:.2f}**. Retorno nominal esperado ajustado = **{mu_spy_anual*100:.2f}% anual**.")

# ==========================================
# 5. MOTOR MATEMÁTICO DE LA DEUDA
# ==========================================
if st.button("🚀 Simular 10 Años (Mes a Mes)", type="primary"):
    barra = st.progress(0)
    
    tasa_mensual_uva = tna_credito / 12
    cuota_uva_fija = saldo_uva * (tasa_mensual_uva * (1 + tasa_mensual_uva)**cuotas_restantes) / ((1 + tasa_mensual_uva)**cuotas_restantes - 1)
    
    mu_spy_mensual = mu_spy_anual / 12
    vol_spy_mensual = 0.15 / np.sqrt(12)
    
    portafolio_A = np.zeros(iteraciones) 
    portafolio_B = np.zeros(iteraciones) 
    
    deuda_A = np.full(iteraciones, float(saldo_uva))
    deuda_B = np.full(iteraciones, float(saldo_uva))
    rutas_costo_uva = np.zeros((iteraciones, meses_simulacion))
    
    brecha_actual_arr = np.full(iteraciones, brecha_inicial_usuario)
    velocidad_reversion_mensual = 0.1 
    
    for mes in range(1, meses_simulacion + 1):
        anio_actual = anio_inicio + (mes // 12)
        
        # --- Lógica de Brecha (Años pares vs impares) ---
        if anio_actual % 2 != 0:
            mu_brecha, vol_brecha = 0.70, 0.07 
        else:
            mu_brecha, vol_brecha = 0.25, 0.03
            
        shock_brecha = np.random.normal(0, vol_brecha, iteraciones)
        brecha_actual_arr = np.maximum(0.0, brecha_actual_arr + velocidad_reversion_mensual * (mu_brecha - brecha_actual_arr) + shock_brecha)
        
        costo_uva_usd_ccl = valor_uva_usd_oficial / (1 + brecha_actual_arr)
        rutas_costo_uva[:, mes-1] = costo_uva_usd_ccl
        
        # --- Generación de Retornos ---
        if distribucion == "Normal (Clásica)":
            retorno_spy = np.random.normal(mu_spy_mensual, vol_spy_mensual, iteraciones)
        else:
            retorno_spy = mu_spy_mensual + np.random.standard_t(df=4, size=iteraciones) * (vol_spy_mensual / np.sqrt(2))
        
        # --- Escenario A (Pagar Cuota + Invertir Resto) ---
        portafolio_A = portafolio_A * (1 + retorno_spy)
        deben_A = (deuda_A > 0)
        costo_cuota_usd = cuota_uva_fija * costo_uva_usd_ccl
        inversion_disponible_A = np.where(deben_A, flujo_mensual_usd - costo_cuota_usd, flujo_mensual_usd)
        deuda_A = np.where(deben_A, deuda_A - (cuota_uva_fija - (deuda_A * tasa_mensual_uva)), 0)
        portafolio_A += inversion_disponible_A
        
        # --- Escenario B (Adelantar a muerte + Invertir luego) ---
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
    # 6. RENDERIZADO DE RESULTADOS
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
        st.success(f"🏆 **Conclusión:** La Opción A (Invertir) te deja en promedio USD {np.mean(diferencia):,.0f} más. Gana en el {probabilidad_A_gana:.1f}% de los escenarios.")
    else:
        st.warning(f"🏆 **Conclusión:** La Opción B (Adelantar) es superior por USD {abs(np.mean(diferencia)):,.0f} extra en promedio. Gana en el {100-probabilidad_A_gana:.1f}% de los escenarios.")

    st.markdown("---")
    st.subheader("📉 Evolución del Costo de 1 UVA en Dólares CCL (Muestra aleatoria)")
    indices_muestra = np.random.choice(iteraciones, 100, replace=False)
    df_uva = pd.DataFrame(rutas_costo_uva[indices_muestra, :].T)
    df_uva.index = range(1, meses_simulacion + 1)
    st.line_chart(df_uva)
