# ==========================================
# 1. EXTRACCIÓN AUTOMÁTICA DE DATOS
# ==========================================
@st.cache_data(ttl=3600) 
def obtener_datos_macro():
    try:
        spy = yf.Ticker("SPY")
        per_actual = spy.info.get('trailingPE', 24.0)
        
        # Le agregamos timeout para que no se quede colgado, y cambiamos a MAYORISTA
        oficial = requests.get("https://dolarapi.com/v1/dolares/mayorista", timeout=5).json()["venta"]
        ccl = requests.get("https://dolarapi.com/v1/dolares/ccl", timeout=5).json()["venta"]
        brecha = (ccl / oficial) - 1
        
        return per_actual, oficial, ccl, brecha, True # El True indica que anduvo perfecto
    except Exception as e:
        # Valores de emergencia y un False para saber que falló
        return 24.0, 1000.0, 1300.0, 0.30, False

per_spy, valor_oficial, valor_ccl, brecha_calculada, api_ok = obtener_datos_macro()

# ==========================================
# 2. INPUTS DEL USUARIO
# ==========================================
# (Tu código de inputs sigue igual...)

# Agregá estas dos líneas justo antes de donde empieza tu "Tablero de Control" 
# para que la app te avise si hay problemas:
if not api_ok:
    st.error("⚠️ Error de conexión: No se pudieron descargar los datos en vivo. Verificá que 'requests' esté en tu requirements.txt. Se están usando datos de simulación (1000 y 1300).")
