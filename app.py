import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(page_title="UVA vs SPY", layout="wide")
st.title("⚖️ Simulación Dinámica: Estrategias UVA vs SPY")

# ==========================================
# 2. EXTRACCIÓN AUTOMÁTICA DE DATOS
# ==========================================
@st.cache_data(ttl=3600) 
def obtener_datos_macro():
    try:
        spy = yf.Ticker("SPY")
        per_actual = spy.info.get('trailingPE', 24.0)
        
        usd_ars = yf.Ticker("USDARS=X").history(period="1d")
        oficial = float(usd_ars['Close'].iloc[-1])
        
        ggal_ars = yf.Ticker("GGAL.BA").history(period="1d")
        ggal_usd = yf.Ticker("GGAL").history(period="1d")
        precio_ggal_ars = float(ggal_ars['Close'].iloc[-1])
        precio_ggal_usd = float(ggal_usd['Close'].iloc[-1])
        
        ccl_calculado = (precio_ggal_ars * 10) / precio_ggal_usd
        brecha_calculada = (ccl_calculado / oficial) - 1
        
        return per_actual, oficial, ccl_calculado, brecha_calculada, True
    except Exception as e:
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
# 4. TABLERO DE CONTROL 
# ==========================================
if not api_ok:
    st.error("⚠️ Error de conexión. Usando datos de simulación temporales.")

st.markdown("### 🔍 Datos Base del Modelo")
colA, colB, colC, colD = st.columns(4)
valor_uva_usd_oficial = valor_uva_pesos / valor_oficial

colA.metric("Dólar Oficial", f"ARS {valor_oficial:,.2f}")
colB.metric("Dólar CCL (ADR)", f"ARS {valor_oficial * (1 + brecha_inicial_usuario):,.2f}")
colC.metric("Brecha Usada", f"{brecha_inicial_usuario*100:.1f}%")
colD.metric("Costo 1 UVA (USD Oficial)", f"USD {valor_uva_usd_oficial:.2f}")

crecimiento_real_g = 0.02
inflacion_usd_i = 0.03
mu_spy_anual = (1 / per_spy) + crecimiento_real_g + inflacion_usd_i

# ==========================================
# 5. MOTOR MATEMÁTICO 
# ==========================================
if st.button("🚀 Simular Estrategias (10 Años)", type="primary"):
    barra = st.progress(0)
    
    tasa_mensual_uva = tna_credito / 12
    cuota_uva_fija = saldo_uva * (tasa_mensual_uva * (1 + tasa_mensual_uva)**cuotas_restantes) / ((1 + tasa_mensual_uva)**cuotas_restantes - 1)
    mu_spy_mensual = mu_spy_anual / 12
    vol_spy_mensual = 0.15 / np.sqrt(12)
    
    # Portafolios
    portafolio_A = np.zeros(iteraciones) # Pagar cuota, SPY el resto
    portafolio_B = np.zeros(iteraciones) # Adelantar al máximo siempre
    portafolio_C = np.zeros(iteraciones) # Guardar USD en años pares, adelantar en impares
    portafolio_D = np.zeros(iteraciones) # SPY en años pares, liquidar y adelantar en impares SI hay ganancia
    
    # Deudas
    deuda_A = np.full(iteraciones, float(saldo_uva))
    deuda_B = np.full(iteraciones, float(saldo_uva))
    deuda_C = np.full(iteraciones, float(saldo_uva))
    deuda_D = np.full(iteraciones, float(saldo_uva))
    
    ahorro_usd_C = np.zeros(iteraciones) 
    
    # Rastreos para Opción D (Rendimiento YTD del SPY)
    spy_acum_index = np.ones(iteraciones)
    spy_inicio_anio = np.ones(iteraciones)
    
    rutas_costo_uva = np.zeros((iteraciones, meses_simulacion))
    brecha_actual_arr = np.full(iteraciones, brecha_inicial_usuario)
    velocidad_reversion_mensual = 0.1 
    
    for mes in range(1, meses_simulacion + 1):
        anio_actual = anio_inicio + (mes // 12)
        es_par = (anio_actual % 2 == 0)
        
        # --- Macro y Brecha ---
        if not es_par:
            mu_brecha, vol_brecha = 0.70, 0.07 
        else:
            mu_brecha, vol_brecha = 0.25, 0.03 
            
        shock_brecha = np.random.normal(0, vol_brecha, iteraciones)
        brecha_actual_arr = np.maximum(0.0, brecha_actual_arr + velocidad_reversion_mensual * (mu_brecha - brecha_actual_arr) + shock_brecha)
        costo_uva_usd_ccl = valor_uva_usd_oficial / (1 + brecha_actual_arr)
        rutas_costo_uva[:, mes-1] = costo_uva_usd_ccl
        
        # --- Retornos SPY y Rastreador YTD para Opción D ---
        if distribucion == "Normal (Clásica)":
            retorno_spy = np.random.normal(mu_spy_mensual, vol_spy_mensual, iteraciones)
        else:
            retorno_spy = mu_spy_mensual + np.random.standard_t(df=4, size=iteraciones) * (vol_spy_mensual / np.sqrt(2))
            
        # Actualizamos índice SPY interno. En enero, marcamos el inicio de año.
        if (mes - 1) % 12 == 0:
            spy_inicio_anio = np.copy(spy_acum_index)
        spy_acum_index = spy_acum_index * (1 + retorno_spy)
        
        rendimiento_ytd_spy = (spy_acum_index / spy_inicio_anio) - 1
        
        # --- Escenario A (Invertir Todo) ---
        portafolio_A = portafolio_A * (1 + retorno_spy)
        deben_A = (deuda_A > 0)
        costo_cuota_usd_A = cuota_uva_fija * costo_uva_usd_ccl
        inversion_disponible_A = np.where(deben_A, flujo_mensual_usd - costo_cuota_usd_A, flujo_mensual_usd)
        deuda_A = np.where(deben_A, deuda_A - (cuota_uva_fija - (deuda_A * tasa_mensual_uva)), 0)
        portafolio_A += inversion_disponible_A
        
        # --- Escenario B (Adelantar Siempre) ---
        portafolio_B = portafolio_B * (1 + retorno_spy)
        deben_B = (deuda_B > 0)
        amortizacion_B = (flujo_mensual_usd / costo_uva_usd_ccl) - (deuda_B * tasa_mensual_uva)
        cancela_B = deben_B & (amortizacion_B >= deuda_B)
        deuda_B_prev = np.copy(deuda_B)
        deuda_B = np.where(deben_B & ~cancela_B, deuda_B - amortizacion_B, 0)
        inv_disp_B = np.where(cancela_B, (amortizacion_B - deuda_B_prev) * costo_uva_usd_ccl, 0)
        inv_disp_B = np.where(~deben_B & ~cancela_B, flujo_mensual_usd, inv_disp_B)
        portafolio_B += inv_disp_B

        # --- Escenario C (Arbitraje Dólar Billete a UVA) ---
        portafolio_C = portafolio_C * (1 + retorno_spy)
        deben_C = (deuda_C > 0)
        if es_par:
            costo_cuota_C = cuota_uva_fija * costo_uva_usd_ccl
            deuda_C = np.where(deben_C, deuda_C - (cuota_uva_fija - (deuda_C * tasa_mensual_uva)), 0)
            ahorro_usd_C = np.where(deben_C, ahorro_usd_C + (flujo_mensual_usd - costo_cuota_C), 0)
            portafolio_C += np.where(~deben_C, flujo_mensual_usd, 0)
        else:
            fondos_disp_C = np.where(deben_C, flujo_mensual_usd + ahorro_usd_C, flujo_mensual_usd)
            amort_extra_C = (fondos_disp_C / costo_uva_usd_ccl) - (deuda_C * tasa_mensual_uva)
            cancela_C = deben_C & (amort_extra_C >= deuda_C)
            deuda_C_prev = np.copy(deuda_C)
            deuda_C = np.where(deben_C & ~cancela_C, deuda_C - amort_extra_C, 0)
            inv_disp_C = np.where(cancela_C, (amort_extra_C - deuda_C_prev) * costo_uva_usd_ccl, 0)
            inv_disp_C = np.where(~deben_C & ~cancela_C, flujo_mensual_usd, inv_disp_C)
            portafolio_C += inv_disp_C
            ahorro_usd_C = np.zeros(iteraciones)

        # --- Escenario D (Arbitraje SPY Inteligente) ---
        portafolio_D = portafolio_D * (1 + retorno_spy)
        deben_D = (deuda_D > 0)
        interes_D = deuda_D * tasa_mensual_uva
        
        # Condición mágica: Solo liquidamos si es año impar Y el mercado está en ganancias Y tenemos deuda
        liquida_D = (~es_par) & (rendimiento_ytd_spy >= 0) & deben_D
        
        # Flujo para los que NO liquidan este mes (Pagan cuota y compran SPY)
        costo_cuota_D = cuota_uva_fija * costo_uva_usd_ccl
        amort_normal_D = cuota_uva_fija - interes_D
        nuevo_deuda_D_no_liq = np.where(deben_D, deuda_D - amort_normal_D, 0)
        nuevo_portafolio_D_no_liq = np.where(deben_D, portafolio_D + (flujo_mensual_usd - costo_cuota_D), portafolio_D + flujo_mensual_usd)
        
        # Flujo para los que SÍ liquidan (Revientan el SPY contra la UVA)
        fondos_disp_D = flujo_mensual_usd + portafolio_D
        amort_extra_D = (fondos_disp_D / costo_uva_usd_ccl) - interes_D
        cancela_D = amort_extra_D >= deuda_D
        nuevo_deuda_D_liq = np.where(cancela_D, 0, deuda_D - amort_extra_D)
        nuevo_portafolio_D_liq = np.where(cancela_D, (amort_extra_D - deuda_D) * costo_uva_usd_ccl, 0)
        
        # Aplicamos el filtro a los resultados del mes
        deuda_D = np.where(liquida_D, nuevo_deuda_D_liq, nuevo_deuda_D_no_liq)
        portafolio_D = np.where(liquida_D, nuevo_portafolio_D_liq, nuevo_portafolio_D_no_liq)

        barra.progress(mes / meses_simulacion)
        
    barra.empty()
    
    # ==========================================
    # 6. RENDERIZADO DE RESULTADOS
    # ==========================================
    st.markdown("---")
    st.header(f"Patrimonio Neto tras 10 años")
    st.write("*(Asumiendo aportes ininterrumpidos de USD 2.000 mensuales)*")
    
    # Grilla 2x2 para comparar las 4 estrategias
    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        st.subheader("Opción A: Invertir Resto en SPY")
        st.metric("Promedio Esperado", f"USD {np.mean(portafolio_A):,.0f}")
        st.caption(f"P5: USD {np.percentile(portafolio_A, 5):,.0f}")
        
    with row1_col2:
        st.subheader("Opción B: Adelanto Constante")
        st.metric("Promedio Esperado", f"USD {np.mean(portafolio_B):,.0f}")
        st.caption(f"P5: USD {np.percentile(portafolio_B, 5):,.0f}")

    st.markdown("<br>", unsafe_allow_html=True)
    
    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        st.subheader("Opción C: Arbitraje Electoral (Dólar Billete)")
        st.metric("Promedio Esperado", f"USD {np.mean(portafolio_C):,.0f}")
        st.caption(f"P5: USD {np.percentile(portafolio_C, 5):,.0f}")

    with row2_col2:
        st.subheader("Opción D: Arbitraje Inteligente (SPY con Filtro)")
        st.metric("Promedio Esperado", f"USD {np.mean(portafolio_D):,.0f}")
        st.caption(f"P5: USD {np.percentile(portafolio_D, 5):,.0f}")
        
    # Análisis Final
    st.markdown("---")
    st.subheader("🏆 Análisis del Ganador")
    promedios = {
        "Opción A (Inversión Pura)": np.mean(portafolio_A),
        "Opción B (Adelanto Constante)": np.mean(portafolio_B),
        "Opción C (Arbitraje Billete)": np.mean(portafolio_C),
        "Opción D (Arbitraje Inteligente SPY)": np.mean(portafolio_D)
    }
    ganador = max(promedios, key=promedios.get)
    st.success(f"Matemáticamente, la estrategia superior en promedio es la **{ganador}**.")
    
    st.write("La Opción D es una estrategia híbrida brillante: aprovecha el interés compuesto de la bolsa, pero usa los 'picos' de la brecha electoral para destruir deuda solo cuando las condiciones son óptimas (SPY en ganancias + UVA barata en USD).")
