import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA
# ==========================================
st.set_page_config(page_title="Simulador Montecarlo Arg", layout="wide")
st.title("📊 Simulador Montecarlo: SPY + Riesgo Electoral Arg")
st.markdown("""
Esta simulación calcula el retorno de tu inversión a 20 años considerando:
1. **Valuación del S&P 500:** Extrae el PER en tiempo real para ajustar el retorno esperado.
2. **Ciclo Electoral Argentino:** Modela la brecha cambiaria expandiéndose en años impares y contrayéndose en años pares.
""")

# ==========================================
# 2. EXTRACCIÓN DE DATOS (Con Caché)
# ==========================================
@st.cache_data(ttl=3600) # Guarda el dato por 1 hora para no saturar la API
def obtener_datos_mercado():
    try:
        spy = yf.Ticker("SPY")
        per_actual = spy.info.get('trailingPE', 24.0)
        return per_actual
    except:
        return 24.0 # Valor por defecto si falla la conexión

per_spy = obtener_datos_mercado()

# Calculamos la Tasa de Retorno Esperada (Earnings Yield + Crecimiento + Inflación USD)
crecimiento_real_g = 0.02
inflacion_usd_i = 0.03
mu_spy = (1 / per_spy) + crecimiento_real_g + inflacion_usd_i

# ==========================================
# 3. INTERFAZ LATERAL (Inputs)
# ==========================================
st.sidebar.header("Parámetros Iniciales")
inversion_usd_ccl = st.sidebar.number_input("Inversión Inicial (USD CCL)", value=10000, step=1000)
brecha_inicial = st.sidebar.slider("Brecha Actual (CCL vs Oficial)", 0.0, 1.5, 0.30, format="%.2f")
iteraciones = st.sidebar.slider("Cantidad de Escenarios", 100, 5000, 1000)

anios_simulacion = 20
anio_inicio = 2026

st.sidebar.markdown("---")
st.sidebar.write(f"**PER Actual SPY:** {per_spy:.2f}")
st.sidebar.write(f"**Retorno Esperado S&P 500:** {mu_spy*100:.2f}%")

# ==========================================
# 4. MOTOR DE SIMULACIÓN
# ==========================================
if st.sidebar.button("🚀 Correr Simulación de 20 Años", type="primary"):
    
    barra_progreso = st.progress(0)
    
    # Matrices para guardar resultados (Filas = Escenarios, Columnas = Años)
    # Le sumamos 1 columna para el Año 0 (hoy)
    rutas_brecha = np.zeros((iteraciones, anios_simulacion + 1))
    rutas_brecha[:, 0] = brecha_inicial
    
    rutas_spy = np.zeros((iteraciones, anios_simulacion + 1))
    rutas_spy[:, 0] = inversion_usd_ccl # Arrancamos con el capital inicial
    
    # Volatilidad histórica del SPY
    volatilidad_spy = 0.16 
    velocidad_reversion_brecha = 0.6
    
    # Simulamos año por año
    for i in range(1, anios_simulacion + 1):
        anio_calendario = anio_inicio + i
        
        # --- A. LÓGICA DE LA BRECHA (Ciclo Electoral) ---
        if anio_calendario % 2 != 0:
            # AÑO IMPAR (Electoral: Expansión de brecha)
            mu_brecha = 0.70
            vol_brecha = 0.25
        else:
            # AÑO PAR (Ajuste: Compresión de brecha)
            mu_brecha = 0.25
            vol_brecha = 0.10
            
        # Generamos el shock aleatorio para todos los escenarios en este año
        shock_brecha = np.random.normal(0, vol_brecha, iteraciones)
        cambio_brecha = velocidad_reversion_brecha * (mu_brecha - rutas_brecha[:, i-1]) + shock_brecha
        
        # Calculamos nueva brecha (np.maximum evita brechas negativas)
        rutas_brecha[:, i] = np.maximum(0.0, rutas_brecha[:, i-1] + cambio_brecha)
        
        # --- B. LÓGICA DEL S&P 500 ---
        # Generamos el retorno del año para todos los escenarios
        retornos_anio = np.random.normal(mu_spy, volatilidad_spy, iteraciones)
        rutas_spy[:, i] = rutas_spy[:, i-1] * (1 + retornos_anio)
        
        barra_progreso.progress(i / anios_simulacion)

    # --- C. CÁLCULO DEL PORTAFOLIO FINAL EN USD CCL ---
    # Asumimos que el dólar oficial sigue la inflación de EEUU (PPA),
    # por ende el valor real de tu portafolio depende de cuánto cobrás al salir por CCL.
    # Impacto Brecha = (1 + Brecha_Final) / (1 + Brecha_Inicial)
    
    impacto_brecha_total = (1 + rutas_brecha) / (1 + brecha_inicial)
    portafolio_final = rutas_spy * impacto_brecha_total

    barra_progreso.empty() # Borramos la barra al terminar

    # ==========================================
    # 5. RESULTADOS Y VISUALIZACIÓN
    # ==========================================
    resultados_año_20 = portafolio_final[:, -1]
    
    st.header("Resultados de la Simulación")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Escenario Promedio (Esperado)", f"USD {np.mean(resultados_año_20):,.0f}")
    col2.metric("Peor Escenario (Percentil 5)", f"USD {np.percentile(resultados_año_20, 5):,.0f}")
    col3.metric("Mejor Escenario (Percentil 95)", f"USD {np.percentile(resultados_año_20, 95):,.0f}")
    
    st.markdown("---")
    st.subheader("Evolución de 100 escenarios al azar")
    
    # Armamos un DataFrame con 100 caminos aleatorios para graficar sin colapsar el navegador
    indices_muestra = np.random.choice(iteraciones, 100, replace=False)
    df_grafico = pd.DataFrame(portafolio_final[indices_muestra, :].T)
    df_grafico.index = range(anio_inicio, anio_inicio + anios_simulacion + 1)
    
    st.line_chart(df_grafico)
    
    st.markdown("""
    > **Nota sobre el gráfico:** Cada línea representa un "universo paralelo". Vas a notar que los saltos o caídas bruscas en conjunto suelen coincidir con los años impares/pares de nuestra lógica electoral incrustada.
    """)
