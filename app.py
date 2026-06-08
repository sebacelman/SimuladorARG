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
    # Asumimos un rendimiento real ajustado por PER del 7% anual y 15% de volatilidad
    mu_spy_mensual = 0.07 / 12
    vol_spy_mensual = 0.15 / np.sqrt(12)
    
    # Matrices de resultados (Iteraciones x Meses)
    portafolio_A = np.zeros(iteraciones) # Pagar cuota e invertir resto
    portafolio_B = np.zeros(iteraciones) # Adelantar todo y luego invertir
    
    # Matrices para rastrear la deuda mes a mes en ambos escenarios
    deuda_A = np.full(iteraciones, float(saldo_uva))
    deuda_B = np.full(iteraciones, float(saldo_uva))
    
    brecha_actual_arr = np.full(iteraciones, brecha_actual)
    velocidad_reversion_mensual = 0.1 # Ajuste más lento por ser mensual
    
    for mes in range(1, meses_simulacion + 1):
        anio_actual = anio_inicio + (mes // 12)
        
        # --- 1. SIMULAR MACROECONOMÍA ---
        if anio_actual % 2 != 0:
            mu_brecha = 0.70 # Año Impar (Electoral)
            vol_brecha = 0.07 # Volatilidad mensual
        else:
            mu_brecha = 0.25 # Año Par
            vol_brecha = 0.03
            
        shock = np.random.normal(0, vol_brecha, iteraciones)
        cambio_brecha = velocidad_reversion_mensual * (mu_brecha - brecha_actual_arr) + shock
        brecha_actual_arr = np.maximum(0.0, brecha_actual_arr + cambio_brecha)
        
        # Costo de 1 UVA en dólares CCL este mes
        costo_uva_usd_ccl = valor_uva_oficial / (1 + brecha_actual_arr)
        
        # Rendimiento del S&P 500 este mes
        retorno_spy = np.random.normal(mu_spy_mensual, vol_spy_mensual, iteraciones)
        
        # --- 2. ESCENARIO A: Cuota Normal + SPY ---
        # Actualizar portafolio existente
        portafolio_A = portafolio_A * (1 + retorno_spy)
        
        # Máscara: ¿Aún debe cuotas?
        deben_A = (deuda_A > 0)
        
        # Los que deben, pagan la cuota. Los que ya pagaron (mes > 83), invierten todo.
        costo_cuota_usd = cuota_uva_fija * costo_uva_usd_ccl
        inversion_disponible_A = np.where(deben_A, flujo_mensual_usd - costo_cuota_usd, flujo_mensual_usd)
        
        # Restar la amortización de la deuda (simplificado)
        deuda_A = np.where(deben_A, deuda_A - (cuota_uva_fija - (deuda_A * tasa_mensual_uva)), 0)
        
        portafolio_A += inversion_disponible_A
        
        # --- 3. ESCENARIO B: Adelantar Capital a Muerte ---
        portafolio_B = portafolio_B * (1 + retorno_spy)
        
        deben_B = (deuda_B > 0)
        
        # Capacidad de compra de UVAs con los USD 2000
        uvas_comprables = flujo_mensual_usd / costo_uva_usd_ccl
        interes_mes_B = deuda_B * tasa_mensual_uva
        amortizacion_B = uvas_comprables - interes_mes_B
        
        # Si la amortización es mayor a la deuda restante, cancela y el resto va al SPY
        cancela_este_mes = deben_B & (amortizacion_B >= deuda_B)
        
        # Actualizamos Deuda B
        deuda_B = np.where(deben_B & ~cancela_este_mes, deuda_B - amortizacion_B, 0)
        
        # Si canceló este mes, calcula cuántos USD sobraron para invertir
        uvas_sobrantes = np.where(cancela_este_mes, amortizacion_B - deuda_B, 0) # Deuda_B antes del cero
        inversion_disponible_B = np.where(cancela_este_mes, uvas_sobrantes * costo_uva_usd_ccl, 0)
        
        # Si ya no debe nada (meses posteriores a la cancelación), invierte los 2000 completos
        inversion_disponible_B = np.where(~deben_B & ~cancela_este_mes, flujo_mensual_usd, inversion_disponible_B)
        
        portafolio_B += inversion_disponible_B
        
        barra.progress(mes / meses_simulacion)
        
    barra.empty()
    
    # ==========================================
    # 4. RESULTADOS (Mes 120 / Año 10)
    # ==========================================
    st.header(f"Patrimonio Neto tras 10 años")
    st.write("*(Asumiendo que en ambos casos seguís aportando USD 2.000 mensuales incluso después de saldar la deuda)*")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Opción A: Pagar Cuota + Invertir")
        st.metric("Promedio Esperado", f"USD {np.mean(portafolio_A):,.0f}")
        st.write(f"Peor Escenario (P5): USD {np.percentile(portafolio_A, 5):,.0f}")
        st.write(f"Mejor Escenario (P95): USD {np.percentile(portafolio_A, 95):,.0f}")
        
    with col2:
        st.subheader("Opción B: Adelantar Capital + Invertir")
        st.metric("Promedio Esperado", f"USD {np.mean(portafolio_B):,.0f}")
        st.write(f"Peor Escenario (P5): USD {np.percentile(portafolio_B, 5):,.0f}")
        st.write(f"Mejor Escenario (P95): USD {np.percentile(portafolio_B, 95):,.0f}")
        
    # Análisis de Diferencia
    diferencia = portafolio_A - portafolio_B
    probabilidad_A_gana = np.sum(diferencia > 0) / iteraciones * 100
    
    st.markdown("---")
    if np.mean(diferencia) > 0:
        st.success(f"🏆 **Conclusión del Modelo:** La Opción A (Invertir) te deja en promedio USD {np.mean(diferencia):,.0f} más rico. Gana en el {probabilidad_A_gana:.1f}% de los escenarios.")
    else:
        st.warning(f"🏆 **Conclusión del Modelo:** La Opción B (Adelantar) es superior, dejándote con USD {abs(np.mean(diferencia)):,.0f} extra en promedio. Gana en el {100-probabilidad_A_gana:.1f}% de los escenarios.")
