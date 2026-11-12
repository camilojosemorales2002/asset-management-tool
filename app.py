import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import ollama

# Configuración inicial de la página en modo ancho
st.set_page_config(page_title="Institutional Equity Research Terminal", layout="wide")

# Estilos CSS avanzados para interfaz negra pulcra, letras blancas y menú desplegable con fondo blanco y letras negras
st.markdown("""
    <style>
    .stApp {
        background-color: #0B0E14;
        color: #FFFFFF;
    }
    /* Estilos de la barra lateral */
    section[data-testid="stSidebar"] {
        background-color: #121820;
    }
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] label, 
    section[data-testid="stSidebar"] span {
        color: #FFFFFF !important;
    }
    /* Contenedor principal del selectbox (caja cerrada) */
    div[data-baseweb="select"] > div {
        background-color: #1A222D !important;
        color: #FFFFFF !important;
        border-color: #2D3748 !important;
    }
    div[data-baseweb="select"] span {
        color: #FFFFFF !important;
    }
    /* Menú desplegable flotante (dropdown menu) con FONDO BLANCO y LETRAS NEGRAS */
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul[data-baseweb="menu"] {
        background-color: #FFFFFF !important;
        color: #000000 !important;
    }
    div[role="option"], div[role="option"] div, span[role="option"] {
        background-color: #FFFFFF !important;
        color: #000000 !important;
    }
    div[role="option"]:hover {
        background-color: #E2E8F0 !important;
        color: #000000 !important;
    }
    /* Textos generales y tarjetas métricas */
    h1, h2, h3, h4, h5, h6, p, span, label, div {
        color: #FFFFFF !important;
    }
    .stMetric {
        background-color: #121820;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #1F2937;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        color: #FFFFFF !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("Terminal Institucional de Equity Research & Valorización")
st.markdown("Plataforma cuantitativa para análisis fundamental, modelamiento DCF y generación de tesis de inversión.")

# Selector categorizado en la barra lateral
st.sidebar.header("Selección de Activos")

categorias_activos = {
    "Acciones Chilenas (IPSA / Principales)": {
        "SQM - Sociedad Química y Minera (SQM-B.SN)": "SQM-B.SN",
        "Banco de Chile (CHILE.SN)": "CHILE.SN",
        "Banco de Crédito e Inversiones - BCI (BCI.SN)": "BCI.SN",
        "Empresas Copec (COPEC.SN)": "COPEC.SN",
        "Falabella (FALABELLA.SN)": "FALABELLA.SN",
        "LATAM Airlines (LTM.SN)": "LTM.SN",
        "CMPC (CMPC.SN)": "CMPC.SN",
        "Enel Americas (ENELAM.SN)": "ENELAM.SN",
        "Cencosud (CENCOSUD.SN)": "CENCOSUD.SN",
        "Parque Arauco (PARAUCO.SN)": "PARAUCO.SN",
        "Colbún (COLBUN.SN)": "COLBUN.SN"
    },
    "Acciones Internacionales (Benchmark)": {
        "Apple Inc. (AAPL)": "AAPL",
        "Microsoft Corp. (MSFT)": "MSFT",
        "Nvidia Corp. (NVDA)": "NVDA",
        "Tesla Inc. (TSLA)": "TSLA",
        "JPMorgan Chase & Co. (JPM)": "JPM"
    },
    "Bonos y Renta Fija (Benchmarks ETF)": {
        "iShares 20+ Year Treasury Bond ETF (TLT)": "TLT",
        "iShares Core US Aggregate Bond ETF (AGG)": "AGG",
        "Vanguard Total International Bond ETF (BNDX)": "BNDX",
        "iShares J.P. Morgan USD Emerging Markets Bond ETF (EMB)": "EMB"
    },
    "Instrumentos de Corto Plazo / Tasas (DAP / Cash Proxy)": {
        "SPDR Bloomberg 1-3 Month T-Bill ETF (BIL)": "BIL",
        "iShares Short Treasury Bond ETF (SHV)": "SHV"
    }
}

categoria_seleccionada = st.sidebar.selectbox("Seleccione Categoría", list(categorias_activos.keys()))
activo_seleccionado = st.sidebar.selectbox("Seleccione el Activo", list(categorias_activos[categoria_seleccionada].keys()))
ticker_symbol = categorias_activos[categoria_seleccionada][activo_seleccionado]

@st.cache_data
def cargar_datos_financieros(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    hist = stock.history(period="1y")
    return info, hist

try:
    with st.spinner(f"Extrayendo datos de mercado para {ticker_symbol}..."):
        info, hist = cargar_datos_financieros(ticker_symbol)

    moneda = info.get('currency', 'USD')

    tab1, tab2, tab3 = st.tabs(["Resumen Financiero y Mercado", "Modelo DCF Interactivo", "Tesis de Research (IA Local)"])

    with tab1:
        st.subheader(f"Perfil Corporativo: {info.get('longName', ticker_symbol)}")
        
        col1, col2, col3, col4 = st.columns(4)
        precio_actual = info.get('currentPrice', info.get('regularMarketPreviousClose', 0.0))
        market_cap = info.get('marketCap', 0)
        per = info.get('trailingPE', 'N/A')
        margen_ebitda = info.get('ebitdaMargins', None)

        # Cálculo de variación diaria estimada para el indicador de color (delta)
        prev_close = info.get('previousClose', precio_actual)
        cambio_diario_pct = ((precio_actual - prev_close) / prev_close) * 100 if prev_close and prev_close > 0 else 0.0

        # Formato numérico limpio, redondeado y sin puntos suspensivos (...)
        precio_str = f"{precio_actual:,.1f} {moneda}" if isinstance(precio_actual, (int, float)) else "N/A"
        
        # Redondeo limpio de Market Cap a miles de millones (B) o millones (M)
        if isinstance(market_cap, (int, float)) and market_cap > 0:
            if market_cap >= 1e9:
                market_cap_str = f"{market_cap / 1e9:,.1f}B {moneda}"
            else:
                market_cap_str = f"{market_cap / 1e6:,.1f}M {moneda}"
        else:
            market_cap_str = "N/A"

        per_str = f"{per:.1f}" if isinstance(per, (int, float)) else "N/A"
        ebitda_str = f"{margen_ebitda*100:.1f}%" if isinstance(margen_ebitda, (int, float)) else "N/A"

        # Métricas con colores condicionales nativos
        col1.metric("Precio Actual", precio_str, delta=f"{cambio_diario_pct:+.1f}% diario", delta_color="normal")
        col2.metric("Market Cap (Aprox)", market_cap_str)
        col3.metric("PER (Trailing)", per_str)
        col4.metric("Margen EBITDA", ebitda_str)

        st.subheader("Evolución Histórica de Precios")
        if not hist.empty:
            # Gráfico interactivo en Azul Neón (#00E5FF) con tema oscuro
            fig = px.line(hist, x=hist.index, y='Close', title=f"Precio de Cierre Histórico - {ticker_symbol} ({moneda})")
            fig.update_traces(line=dict(color='#00E5FF', width=2.5))
            fig.update_layout(
                plot_bgcolor='#121820',
                paper_bgcolor='#0B0E14',
                font=dict(color='white'),
                yaxis=dict(title=f"Precio en {moneda}", gridcolor='#1F2937', zerolinecolor='#1F2937'),
                xaxis=dict(title="Fecha", gridcolor='#1F2937', zerolinecolor='#1F2937', rangeslider=dict(visible=True))
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No hay suficientes datos históricos disponibles para graficar este activo.")

        st.markdown("---")
        st.subheader("Insights Clave del Activo")
        col_i1, col_i2 = st.columns(2)
        with col_i1:
            st.write(f"**Sector:** {info.get('sector', 'N/A')}")
            st.write(f"**Industria:** {info.get('industry', 'N/A')}")
            st.write(f"**Beta:** {info.get('beta', 'N/A')}")
        with col_i2:
            div_yield = info.get('dividendYield', None)
            div_str = f"{div_yield*100:.1f}%" if isinstance(div_yield, (int, float)) else "N/A"
            st.write(f"**Dividendo Yield:** {div_str}")
            st.write(f"**Ratio Deuda / Patrimonio:** {info.get('debtToEquity', 'N/A')}")
            st.write(f"**Moneda Base:** {moneda}")

    with tab2:
        st.subheader("Supuestos de Valorización por Flujo de Caja Descontado (DCF)")
        st.markdown("Modifique los supuestos operativos para evaluar el valor intrínseco de la compañía frente a su cotización de mercado.")

        col_a, col_b = st.columns(2)
        with col_a:
            flujo_base_default = float(info.get('freeCashflow', 1000000000)) / 1e6 if info.get('freeCashflow') else 1000.0
            ingreso_base = st.number_input(f"Flujo de Caja Libre Base (FCFF en millones {moneda})", value=abs(flujo_base_default), step=100.0)
            cagr_proyectado = st.slider("Crecimiento Anual Esperado de Ingresos (CAGR %)", 0.0, 20.0, 5.0, 0.5) / 100
            margen_fcc = st.slider("Conversión de Flujo / Margen Operativo Libre (%)", 5.0, 50.0, 20.0, 1.0) / 100
        
        with col_b:
            wacc = st.slider("Tasa de Descuento WACC (%)", 5.0, 18.0, 9.0, 0.25) / 100
            g_terminal = st.slider("Tasa de Crecimiento Terminal (g %)", 1.0, 4.0, 2.0, 0.25) / 100
            anos_proyeccion = st.slider("Horizonte de Proyección (Años)", 3, 10, 5)

        flujos_proyectados = []
        flujo_actual = ingreso_base
        for i in range(1, anos_proyeccion + 1):
            flujo_actual *= (1 + cagr_proyectado)
            fcc_anual = flujo_actual * margen_fcc
            valor_presente = fcc_anual / ((1 + wacc) ** i)
            flujos_proyectados.append({
                "Año": f"Año {i}",
                f"FCF Proyectado ({moneda}M)": round(fcc_anual, 1),
                f"Valor Presente ({moneda}M)": round(valor_presente, 1)
            })

        df_dcf = pd.DataFrame(flujos_proyectados)
        suma_vp = df_dcf[f"Valor Presente ({moneda}M)"].sum()

        ultimo_fcc = df_dcf[f"FCF Proyectado ({moneda}M)"].iloc[-1]
        if wacc <= g_terminal:
            st.error("Error analítico: El WACC debe ser estrictamente mayor que la tasa de crecimiento terminal (g).")
        else:
            valor_terminal = (ultimo_fcc * (1 + g_terminal)) / (wacc - g_terminal)
            vp_terminal = valor_terminal / ((1 + wacc) ** anos_proyeccion)

            enterprise_value = suma_vp + vp_terminal
            acciones_en_circulacion = info.get('sharesOutstanding', 1e9)
            if not acciones_en_circulacion or acciones_en_circulacion == 0:
                acciones_en_circulacion = 1e9

            equity_value_per_share = (enterprise_value * 1e6) / acciones_en_circulacion

            st.markdown("---")
            res_col1, res_col2, res_col3 = st.columns(3)
            res_col1.metric("Valor Empresa (EV Estimado)", f"{enterprise_value:,.1f}M {moneda}")
            res_col2.metric("Precio Objetivo por Acción", f"{equity_value_per_share:,.1f} {moneda}")
            
            if isinstance(precio_actual, (int, float)) and precio_actual > 0:
                diff_precio = ((equity_value_per_share - precio_actual) / precio_actual) * 100
                res_col3.metric("Potencial de Retorno", f"{diff_precio:+.1f}%", delta=f"{diff_precio:+.1f}%", delta_color="normal")
            else:
                res_col3.metric("Potencial de Retorno", "N/A")

            st.subheader("Proyección Detallada de Flujos de Caja Libres")
            st.dataframe(df_dcf, use_container_width=True)

    with tab3:
        st.subheader("Generación de Tesis de Inversión Automatizada (Ollama Local)")
        st.markdown("Síntesis ejecutiva de análisis fundamental basada en los datos extraídos y el modelo DCF calculado.")
        
        if st.button("Generar Reporte Institucional de Research"):
            with st.spinner("Procesando matriz de riesgos y redactando tesis formal..."):
                prompt_text = f"""
                Actúa como un analista senior de Equity Research en una institución financiera de primer nivel.
                Analiza los siguientes datos fundamentales y de mercado de la empresa {ticker_symbol} ({info.get('longName', 'Empresa')}):
                - Moneda: {moneda}
                - Sector: {info.get('sector', 'N/A')}
                - P/E Ratio: {per_str}
                - Margen EBITDA: {ebitda_str}
                - Precio de Mercado actual: {precio_actual} {moneda}
                - Precio Objetivo estimado por DCF: {equity_value_per_share:,.1f} {moneda}

                Redacta un reporte formal, riguroso y estructurado en español con los siguientes apartados:
                1. Tesis de Inversión Fundamental.
                2. Drivers de Crecimiento y Supuestos de Valorización.
                3. Matriz de Principales Riesgos de Mercado.
                4. Recomendación Final de Inversión (Compra / Mantener / Venta) debidamente justificada.
                """
                
                response = ollama.chat(model='llama3', messages=[
                    {'role': 'user', 'content': prompt_text},
                ])
                
                st.success("Reporte institucional generado exitosamente.")
                st.write(response['message']['content'])

except Exception as e:
    st.error(f"Error al procesar el activo financiero: {e}. Verifique la conexión o el nemotécnico seleccionado.")
