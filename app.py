"""
Terminal de Equity Research — Chile y mercados globales
Autor: Camilo José Morales Carvajal

Análisis por tipo de activo:
  - Empresas (Chile por sector e internacionales): DCF con deuda neta y sensibilidad WACC / g
  - Bancos (Chile e internacionales): P/B justificado (Gordon): P/B = (ROE − g) / (Ke − g)
  - Comparables sectoriales: múltiplos de todas las empresas del mismo grupo
  - ETFs y Macro global: rentabilidad, riesgo, comparación base 100 y correlaciones
  - Indicadores Chile (Banco Central vía mindicador.cl): UF, IPC, IMACEC, TPM, desempleo, dólar, cobre
  - Tesis con IA local (opcional, requiere Ollama en el equipo)
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

# Ollama es opcional: funciona en local, no en Streamlit Cloud
try:
    import ollama
    OLLAMA = True
except ImportError:
    OLLAMA = False

st.set_page_config(page_title="Terminal de Equity Research", layout="wide")

# ---------------------------------------------------------------------------
# Universo de activos
# ---------------------------------------------------------------------------
ACTIVOS = {
    "Chile · Bancos y financieras": {
        "Banco de Chile": "CHILE.SN",
        "BCI": "BCI.SN",
        "Banco Santander Chile": "BSANTANDER.SN",
        "Banco Itaú Chile": "ITAUCL.SN",
        "Bicecorp (Banco BICE + Security)": "BICE.SN",
        "ILC (Banco Internacional, Confuturo)": "ILC.SN",
    },
    "Chile · Minería, química y forestal": {
        "SQM-B": "SQM-B.SN",
        "CAP": "CAP.SN",
        "CMPC": "CMPC.SN",
    },
    "Chile · Energía y servicios básicos": {
        "Empresas Copec": "COPEC.SN",
        "Enel Chile": "ENELCHILE.SN",
        "Enel Américas": "ENELAM.SN",
        "Colbún": "COLBUN.SN",
        "Engie Energía Chile": "ECL.SN",
        "Aguas Andinas": "AGUAS-A.SN",
        "IAM (Aguas Metropolitanas)": "IAM.SN",
    },
    "Chile · Consumo y retail": {
        "Falabella": "FALABELLA.SN",
        "Cencosud": "CENCOSUD.SN",
        "Ripley": "RIPLEY.SN",
        "SMU (Unimarc)": "SMU.SN",
        "CCU": "CCU.SN",
        "Embotelladora Andina": "ANDINA-B.SN",
        "Concha y Toro": "CONCHATORO.SN",
    },
    "Chile · Inmobiliario y construcción": {
        "Parque Arauco": "PARAUCO.SN",
        "Mallplaza": "MALLPLAZA.SN",
        "Cencosud Shopping": "CENCOMALLS.SN",
        "SalfaCorp": "SALFACORP.SN",
    },
    "Chile · Transporte, telecom y holdings": {
        "LATAM Airlines": "LTM.SN",
        "Vapores (CSAV)": "VAPORES.SN",
        "Entel": "ENTEL.SN",
        "Quiñenco": "QUINENCO.SN",
    },
    "Bancos internacionales": {
        "JPMorgan Chase": "JPM",
        "Bank of America": "BAC",
        "Citigroup": "C",
        "Itaú Unibanco (Brasil)": "ITUB",
        "Banco Santander (España)": "SAN",
        "Credicorp (Perú)": "BAP",
    },
    "Pares globales: cobre y litio": {
        "Freeport-McMoRan": "FCX",
        "Southern Copper": "SCCO",
        "Teck Resources": "TECK",
        "Albemarle (litio)": "ALB",
    },
    "Acciones internacionales": {
        "Apple": "AAPL",
        "Microsoft": "MSFT",
        "Nvidia": "NVDA",
        "Amazon": "AMZN",
        "Alphabet (Google)": "GOOGL",
        "Meta": "META",
        "Tesla": "TSLA",
    },
    "ETFs": {
        "iShares MSCI Chile (ECH)": "ECH",
        "América Latina 40 (ILF)": "ILF",
        "Mercados Emergentes (EEM)": "EEM",
        "S&P 500 (SPY)": "SPY",
        "Nasdaq 100 (QQQ)": "QQQ",
        "Mineras de Cobre (COPX)": "COPX",
        "Litio y baterías (LIT)": "LIT",
        "Oro (GLD)": "GLD",
        "Bonos Tesoro 20+ años (TLT)": "TLT",
        "Bonos Tesoro 7-10 años (IEF)": "IEF",
        "Bonos agregados EE.UU. (AGG)": "AGG",
        "Bonos Emergentes USD (EMB)": "EMB",
        "T-Bills 1-3 meses (BIL)": "BIL",
    },
    "Macro global": {
        "IPSA": "^IPSA",
        "S&P 500": "^GSPC",
        "Bovespa (Brasil)": "^BVSP",
        "Shanghai Composite (China)": "000001.SS",
        "Dólar (USD/CLP)": "CLP=X",
        "Real brasileño (USD/BRL)": "BRL=X",
        "Yuan chino (USD/CNY)": "CNY=X",
        "Cobre (USD/lb)": "HG=F",
        "Petróleo WTI (USD/bbl)": "CL=F",
        "Petróleo Brent (USD/bbl)": "BZ=F",
        "Oro (USD/oz)": "GC=F",
        "Tasa Tesoro EE.UU. 10 años (%)": "^TNX",
        "Tasa Tesoro EE.UU. 3 meses (%)": "^IRX",
        "Índice Dólar (DXY)": "DX-Y.NYB",
        "Volatilidad VIX": "^VIX",
    },
    "Indicadores Chile (Banco Central)": {},  # se llenan desde mindicador.cl
}

# Tickers alternativos por si Yahoo cambia el nemotécnico (ej.: BICECORP pasó a BICE)
ALTERNATIVOS = {"BICE.SN": ["BICECORP.SN"]}


def tipo_de(categoria: str) -> str:
    if "Bancos" in categoria:
        return "banco"
    if categoria.startswith("Chile ·") or categoria in ("Pares globales: cobre y litio", "Acciones internacionales"):
        return "empresa"
    if categoria == "ETFs":
        return "etf"
    if categoria == "Indicadores Chile (Banco Central)":
        return "indicador_cl"
    return "macro"


TODOS = {n: t for grupo in ACTIVOS.values() for n, t in grupo.items()}

COMPARAR_POR_DEFECTO = {
    "Chile · Bancos y financieras": ["IPSA", "Banco de Chile", "BCI", "Banco Santander Chile"],
    "Chile · Minería, química y forestal": ["IPSA", "Cobre (USD/lb)", "Dólar (USD/CLP)", "Litio y baterías (LIT)"],
    "Chile · Energía y servicios básicos": ["IPSA", "Petróleo Brent (USD/bbl)", "Tasa Tesoro EE.UU. 10 años (%)"],
    "Chile · Consumo y retail": ["IPSA", "Dólar (USD/CLP)"],
    "Chile · Inmobiliario y construcción": ["IPSA", "Tasa Tesoro EE.UU. 10 años (%)"],
    "Chile · Transporte, telecom y holdings": ["IPSA", "Petróleo Brent (USD/bbl)", "Dólar (USD/CLP)"],
    "Bancos internacionales": ["S&P 500", "Tasa Tesoro EE.UU. 10 años (%)"],
    "Pares globales: cobre y litio": ["Cobre (USD/lb)", "SQM-B", "Mineras de Cobre (COPX)"],
    "Acciones internacionales": ["S&P 500", "Nasdaq 100 (QQQ)"],
    "ETFs": ["S&P 500", "iShares MSCI Chile (ECH)"],
    "Macro global": ["IPSA", "Cobre (USD/lb)", "Dólar (USD/CLP)", "Shanghai Composite (China)"],
}

INDICADORES_CL = {  # nombre: (código mindicador.cl, unidad, es_tasa)
    "UF": ("uf", "CLP", False),
    "Dólar observado": ("dolar", "CLP", False),
    "Euro": ("euro", "CLP", False),
    "Cobre BCCh (USD/lb)": ("libra_cobre", "USD", False),
    "IPC (variación mensual)": ("ipc", "%", True),
    "IMACEC (variación anual)": ("imacec", "%", True),
    "Tasa de Política Monetaria": ("tpm", "%", True),
    "Tasa de desempleo": ("tasa_desempleo", "%", True),
}

PERIODOS = {"6 meses": "6mo", "1 año": "1y", "3 años": "3y", "5 años": "5y"}
ANIOS_PERIODO = {"6mo": 0.5, "1y": 1, "3y": 3, "5y": 5}


# ---------------------------------------------------------------------------
# Datos (con caché para no saturar las fuentes)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def _historial_simple(ticker: str, periodo: str) -> pd.Series:
    try:
        df = yf.Ticker(ticker).history(period=periodo)
    except Exception:
        return pd.Series(dtype=float)
    if df.empty:
        return pd.Series(dtype=float)
    serie = df["Close"].copy()
    serie.index = pd.to_datetime(serie.index).tz_localize(None).normalize()
    return serie[~serie.index.duplicated()].dropna()


def resolver(ticker: str) -> str:
    """Devuelve el primer ticker (original o alternativo) que tenga datos."""
    for t in [ticker] + ALTERNATIVOS.get(ticker, []):
        if not _historial_simple(t, "5d").empty:
            return t
    return ticker


def historial(ticker: str, periodo: str) -> pd.Series:
    return _historial_simple(resolver(ticker), periodo)


@st.cache_data(ttl=3600, show_spinner=False)
def ficha(ticker: str) -> dict:
    try:
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def dividendos(ticker: str) -> pd.Series:
    try:
        div = yf.Ticker(ticker).dividends
        if div.empty:
            return pd.Series(dtype=float)
        div.index = pd.to_datetime(div.index).tz_localize(None)
        return div
    except Exception:
        return pd.Series(dtype=float)


def dividendos_12m(ticker: str) -> float:
    div = dividendos(ticker)
    if div.empty:
        return 0.0
    return float(div[div.index >= pd.Timestamp.now() - pd.DateOffset(years=1)].sum())


@st.cache_data(ttl=3600, show_spinner=False)
def tipo_de_cambio(desde: str, hacia: str):
    """Convierte la moneda de los estados financieros a la de cotización
    (ej.: SQM reporta en USD pero cotiza en CLP)."""
    if not desde or not hacia or desde == hacia:
        return 1.0
    serie = _historial_simple(f"{desde}{hacia}=X", "5d")
    return float(serie.iloc[-1]) if not serie.empty else None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def serie_mindicador(codigo: str, anios: float) -> pd.Series:
    """Series del Banco Central de Chile publicadas por mindicador.cl (API pública, sin clave)."""
    hoy = pd.Timestamp.now()
    datos = []
    for anio in range(hoy.year - int(np.ceil(anios)) - 1, hoy.year + 1):
        try:
            r = requests.get(f"https://mindicador.cl/api/{codigo}/{anio}", timeout=10)
            r.raise_for_status()
            datos += r.json().get("serie", [])
        except Exception:
            continue
    if not datos:
        return pd.Series(dtype=float)
    fechas = (pd.to_datetime([d["fecha"] for d in datos], utc=True)
              .tz_convert("America/Santiago").tz_localize(None).normalize())
    serie = pd.Series([d["valor"] for d in datos], index=fechas, dtype=float).sort_index()
    serie = serie[~serie.index.duplicated()]
    return serie[serie.index >= hoy - pd.DateOffset(months=int(anios * 12))]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def es_num(x):
    return isinstance(x, (int, float, np.floating)) and np.isfinite(x)


def pct(x, dec=1, signo=True):
    if not es_num(x):
        return "N/A"
    return f"{x * 100:+.{dec}f}%" if signo else f"{x * 100:.{dec}f}%"


def num(x, dec=1, sufijo=""):
    return f"{x:,.{dec}f}{sufijo}" if es_num(x) else "N/A"


def metricas_riesgo(serie: pd.Series) -> dict:
    retornos = serie.pct_change().dropna()

    def retorno(meses):
        """Retorno desde la misma fecha hace N meses (tolera unos días de diferencia por feriados)."""
        objetivo = serie.index[-1] - pd.DateOffset(months=meses)
        if serie.index[0] > objetivo + pd.Timedelta(days=10):
            return None
        anteriores = serie[serie.index <= objetivo]
        base = anteriores.iloc[-1] if not anteriores.empty else serie.iloc[0]
        return serie.iloc[-1] / base - 1

    anio_actual = serie[serie.index.year == serie.index[-1].year]
    return {
        "1 mes": retorno(1),
        "3 meses": retorno(3),
        "Año a la fecha": anio_actual.iloc[-1] / anio_actual.iloc[0] - 1 if len(anio_actual) > 1 else None,
        "1 año": retorno(12),
        "Volatilidad anual": retornos.std() * np.sqrt(252),
        "Máxima caída": (serie / serie.cummax() - 1).min(),
    }


def rsi(serie: pd.Series, n: int = 14):
    delta = serie.diff()
    subida = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    bajada = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    valor = 100 - 100 / (1 + subida.iloc[-1] / bajada.iloc[-1]) if bajada.iloc[-1] > 0 else 100.0
    return float(valor)


def grafico_linea(df, titulo, eje_y):
    fig = px.line(df, title=titulo)
    fig.update_layout(xaxis_title=None, yaxis_title=eje_y, legend_title=None, hovermode="x unified")
    return fig


def tabla(diccionario, columnas=("Indicador", "Valor")):
    st.dataframe(pd.DataFrame(list(diccionario.items()), columns=list(columnas)), hide_index=True)


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
st.sidebar.header("Selección")
categoria = st.sidebar.selectbox("Categoría", list(ACTIVOS.keys()))
tipo = tipo_de(categoria)
opciones_activo = list(INDICADORES_CL.keys()) if tipo == "indicador_cl" else list(ACTIVOS[categoria].keys())
nombre = st.sidebar.selectbox("Activo / indicador", opciones_activo)
periodo_txt = st.sidebar.radio("Período", list(PERIODOS.keys()), index=1, horizontal=True)
periodo = PERIODOS[periodo_txt]

st.sidebar.markdown("---")
st.sidebar.caption("Fuentes: Yahoo Finance y Banco Central de Chile (vía mindicador.cl). "
                   "Los datos pueden tener retraso. Uso educativo, no es recomendación de inversión.")

# ===========================================================================
# INDICADORES CHILE (Banco Central)
# ===========================================================================
if tipo == "indicador_cl":
    codigo, unidad, es_tasa = INDICADORES_CL[nombre]
    st.title(nombre)
    st.caption("Fuente: Banco Central de Chile / INE vía mindicador.cl")

    tab_ind, tab_panel = st.tabs(["Indicador", "Panel Chile"])

    with tab_ind:
        with st.spinner("Descargando serie..."):
            serie = serie_mindicador(codigo, max(ANIOS_PERIODO[periodo], 1.0) + 1)
        if serie.empty:
            st.error("No se pudo conectar con mindicador.cl. Intente de nuevo en unos minutos.")
        else:
            ultimo = serie.iloc[-1]
            hace_un_anio = serie[serie.index <= serie.index[-1] - pd.DateOffset(years=1)]
            visible = serie[serie.index >= serie.index[-1] - pd.DateOffset(months=int(ANIOS_PERIODO[periodo] * 12))]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric(f"Último dato ({serie.index[-1]:%d-%m-%Y})",
                      num(ultimo, 2, "%" if es_tasa else f" {unidad}"))
            if not hace_un_anio.empty:
                base = hace_un_anio.iloc[-1]
                if es_tasa:
                    c2.metric("Cambio en 12 meses", f"{ultimo - base:+.2f} pp")
                else:
                    c2.metric("Variación 12 meses", pct(ultimo / base - 1))
            c3.metric("Máximo del período", num(visible.max(), 2))
            c4.metric("Mínimo del período", num(visible.min(), 2))

            if codigo == "ipc":
                ultimos_12 = serie.iloc[-12:]
                inflacion_12m = np.prod(1 + ultimos_12 / 100) - 1
                st.info(f"**Inflación acumulada últimos 12 meses: {inflacion_12m:.1%}** "
                        "(la meta del Banco Central es 3%).")

            if es_tasa and codigo != "tpm":
                fig = px.bar(visible, title=f"{nombre} — {periodo_txt}")
                fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title="%")
            else:
                fig = grafico_linea(visible.rename(nombre), f"{nombre} — {periodo_txt}", unidad)
                if codigo == "tpm":
                    fig.update_traces(line_shape="hv")
            st.plotly_chart(fig)

            explicaciones = {
                "uf": "La UF se reajusta diariamente según el IPC del mes anterior. Su variación anual es, en la práctica, la inflación.",
                "dolar": "Un dólar alto encarece importaciones y combustibles, pero favorece a exportadores (minería, celulosa, vino, salmón).",
                "euro": "Relevante para importaciones desde Europa y para empresas con operaciones en la zona euro.",
                "libra_cobre": "El cobre es cerca de la mitad de las exportaciones chilenas: impacta el peso, la recaudación fiscal y el IPSA.",
                "ipc": "La inflación determina la UF, los reajustes de arriendos y créditos, y las decisiones de tasa del Banco Central.",
                "imacec": "Indicador mensual de actividad económica: aproxima el crecimiento del PIB.",
                "tpm": "Tasa de referencia del Banco Central. TPM más baja abarata el crédito y suele favorecer a acciones y bonos.",
                "tasa_desempleo": "Desempleo alto presiona el consumo, el retail y la calidad de cartera de los bancos.",
            }
            st.caption(explicaciones.get(codigo, ""))

    with tab_panel:
        st.subheader("Panel macroeconómico de Chile")
        series_panel = {}
        with st.spinner("Cargando todos los indicadores..."):
            for nom, (cod, uni, tasa) in INDICADORES_CL.items():
                series_panel[nom] = (serie_mindicador(cod, 2), uni, tasa)

        columnas = st.columns(4)
        for i, (nom, (s, uni, tasa)) in enumerate(series_panel.items()):
            if s.empty:
                columnas[i % 4].metric(nom, "N/A")
                continue
            previo = s[s.index <= s.index[-1] - pd.DateOffset(years=1)]
            delta = None
            if not previo.empty:
                delta = f"{s.iloc[-1] - previo.iloc[-1]:+.2f} pp 12m" if tasa else f"{pct(s.iloc[-1] / previo.iloc[-1] - 1)} 12m"
            columnas[i % 4].metric(nom, num(s.iloc[-1], 2, "%" if tasa else ""), delta=delta,
                                   delta_color="off" if tasa else "normal")

        col_a, col_b = st.columns(2)
        tpm, ipc = series_panel["Tasa de Política Monetaria"][0], series_panel["IPC (variación mensual)"][0]
        if not tpm.empty and len(ipc) >= 12:
            inflacion = ((1 + ipc / 100).rolling(12).apply(np.prod, raw=True) - 1).dropna() * 100
            df_tasas = pd.concat({"TPM (%)": tpm.resample("ME").last(),
                                  "Inflación 12m (%)": inflacion.resample("ME").last()}, axis=1).dropna()
            if not df_tasas.empty:
                df_tasas["Tasa real (%)"] = df_tasas["TPM (%)"] - df_tasas["Inflación 12m (%)"]
                col_a.plotly_chart(grafico_linea(df_tasas, "Política monetaria: TPM vs inflación", "%"))
        imacec, desempleo = series_panel["IMACEC (variación anual)"][0], series_panel["Tasa de desempleo"][0]
        if not imacec.empty and not desempleo.empty:
            df_act = pd.concat({"IMACEC (%)": imacec.resample("ME").last(),
                                "Desempleo (%)": desempleo.resample("ME").last()}, axis=1)
            col_b.plotly_chart(grafico_linea(df_act, "Actividad y empleo", "%"))
        st.caption("Tasa real = TPM − inflación de 12 meses. Positiva: política monetaria contractiva; "
                   "negativa: expansiva.")

    st.stop()

# ===========================================================================
# ACTIVOS DE MERCADO (Yahoo Finance)
# ===========================================================================
ticker_original = ACTIVOS[categoria][nombre]
with st.spinner(f"Descargando datos de {nombre}..."):
    ticker = resolver(ticker_original)
    precios = historial(ticker, periodo)
    precios_largo = historial(ticker, "5y")
    if precios_largo.empty:
        precios_largo = precios
    info = ficha(ticker) if tipo != "macro" else {}

if precios.empty or len(precios) < 2:
    st.error(f"No se pudieron obtener datos para {nombre} ({ticker}). Intente de nuevo en unos minutos.")
    st.stop()

moneda = info.get("currency", "")
precio = float(precios.iloc[-1])
riesgo = metricas_riesgo(precios)

# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------
st.title(nombre)
detalle = [ticker, categoria]
if info.get("sector"):
    detalle.append(f"{info['sector']} · {info.get('industry', '')}")
st.caption(" · ".join(detalle))

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Último valor", num(precio, 2, f" {moneda}" if moneda else ""),
          delta=pct(precio / precios.iloc[-2] - 1, 2) + " diario")
c2.metric("Retorno 1 año", pct(metricas_riesgo(precios_largo)["1 año"]))
c3.metric("Año a la fecha", pct(riesgo["Año a la fecha"]))
c4.metric("Volatilidad anual", pct(riesgo["Volatilidad anual"], signo=False))
c5.metric("Máxima caída", pct(riesgo["Máxima caída"]))

# ---------------------------------------------------------------------------
# Pestañas según tipo de activo
# ---------------------------------------------------------------------------
pestanas = ["Resumen"]
if tipo == "empresa":
    pestanas.append("Valorización DCF")
if tipo == "banco":
    pestanas.append("Valorización bancaria (P/B)")
if tipo in ("empresa", "banco"):
    pestanas += ["Comparables del sector", "Dividendos"]
pestanas.append("Comparar y correlaciones")
if tipo in ("empresa", "banco"):
    pestanas.append("Tesis con IA")

tabs = dict(zip(pestanas, st.tabs(pestanas)))
valorizacion = {}  # resultados para la tesis con IA

moneda_fin = info.get("financialCurrency", moneda) or moneda
fx = tipo_de_cambio(moneda_fin, moneda) if tipo in ("empresa", "banco") else 1.0
if fx is None:
    fx = 1.0

# ---------------------------- Resumen --------------------------------------
with tabs["Resumen"]:
    mostrar_mm = st.checkbox("Mostrar medias móviles de 50 y 200 días", value=tipo != "macro")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=precios.index, y=precios, name=nombre, line=dict(width=2.2)))
    if mostrar_mm:
        for ventana, color in ((50, "#F6AD55"), (200, "#B794F4")):
            mm = precios_largo.rolling(ventana).mean().reindex(precios.index)
            fig.add_trace(go.Scatter(x=mm.index, y=mm, name=f"Media {ventana} días",
                                     line=dict(width=1.3, dash="dot", color=color)))
    fig.update_layout(title=f"Evolución — {periodo_txt}", yaxis_title=moneda or "Nivel",
                      hovermode="x unified", legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig)

    col_izq, col_med, col_der = st.columns(3)
    with col_izq:
        st.subheader("Rentabilidad y riesgo")
        tabla({k: pct(v, signo=k != "Volatilidad anual") for k, v in riesgo.items()})

    with col_med:
        st.subheader("Técnico")
        mm200 = precios_largo.rolling(200).mean().iloc[-1]
        mm50 = precios_largo.rolling(50).mean().iloc[-1]
        valor_rsi = rsi(precios)
        lectura_rsi = "sobrecompra" if valor_rsi > 70 else "sobreventa" if valor_rsi < 30 else "neutral"
        maximo_52 = precios_largo.iloc[-252:].max()
        minimo_52 = precios_largo.iloc[-252:].min()
        tabla({
            "RSI 14 días": f"{valor_rsi:.0f} ({lectura_rsi})",
            "Precio vs media 200 días": pct(precio / mm200 - 1) if es_num(mm200) else "N/A",
            "Tendencia (media 50 vs 200)": ("Alcista" if mm50 > mm200 else "Bajista") if es_num(mm200) else "N/A",
            "Máximo 52 semanas": num(maximo_52, 2),
            "Mínimo 52 semanas": num(minimo_52, 2),
            "Distancia al máximo": pct(precio / maximo_52 - 1),
        })

    with col_der:
        if tipo in ("empresa", "banco"):
            st.subheader("Fundamentales")
            valor_libro = info.get("bookValue")
            fundamentales = {
                "PER (últimos 12 meses)": num(info.get("trailingPE"), 1, "x"),
                "PER esperado": num(info.get("forwardPE"), 1, "x"),
                "Precio / Valor libro": num(precio / (valor_libro * fx), 2, "x") if es_num(valor_libro) and valor_libro > 0 else "N/A",
                "ROE": pct(info.get("returnOnEquity"), signo=False),
                "Dividend yield (12m)": pct(dividendos_12m(ticker) / precio, signo=False),
                "Beta": num(info.get("beta"), 2),
            }
            if tipo == "empresa":
                fundamentales["Margen EBITDA"] = pct(info.get("ebitdaMargins"), signo=False)
                fundamentales["Deuda / Patrimonio"] = num(info.get("debtToEquity"), 1, "%")
            tabla(fundamentales)
        elif tipo == "etf":
            st.subheader("Información del ETF")
            tabla({
                "Categoría": info.get("category", "N/A"),
                "Activos administrados": num((info.get("totalAssets") or np.nan) / 1e9, 1, " mil millones USD"),
                "Rendimiento por distribuciones (12m)": pct(dividendos_12m(ticker) / precio, signo=False),
                "Beta (3 años)": num(info.get("beta3Year"), 2),
            })
        else:
            st.subheader("Cómo afecta a Chile")
            st.markdown(
                "- **Cobre** alto → peso chileno más fuerte, más recaudación fiscal y mejor IPSA.\n"
                "- **China** compra cerca de 40% de las exportaciones chilenas: su bolsa y el yuan anticipan demanda de cobre y litio.\n"
                "- **Petróleo** alto encarece combustibles, transporte (LATAM) y presiona la inflación.\n"
                "- **Tasas de EE.UU. y DXY** altos fortalecen el dólar y restan atractivo a emergentes.\n"
                "- **VIX** sobre 25–30 indica estrés global; los emergentes suelen caer más."
            )

    if tipo in ("empresa", "banco", "etf") and info.get("longBusinessSummary"):
        with st.expander("Descripción del negocio"):
            st.write(info["longBusinessSummary"])

# ---------------------------- DCF (empresas) --------------------------------
if tipo == "empresa":
    with tabs["Valorización DCF"]:
        st.markdown(
            f"Flujo de caja libre descontado. Estados financieros en **{moneda_fin}**, acción cotiza en **{moneda}**"
            + (f" (tipo de cambio usado: {fx:,.2f})." if fx != 1 else ".")
        )

        fcf_dato = (info.get("freeCashflow") or 0) / 1e6
        deuda_neta_dato = ((info.get("totalDebt") or 0) - (info.get("totalCash") or 0)) / 1e6
        acciones = info.get("sharesOutstanding")

        col_a, col_b = st.columns(2)
        with col_a:
            fcf0 = st.number_input(f"Flujo de caja libre último año (millones {moneda_fin})",
                                   value=float(round(fcf_dato, 1)), step=100.0)
            crecimiento = st.slider("Crecimiento anual del flujo (%)", -5.0, 25.0, 5.0, 0.5) / 100
            anios = st.slider("Años de proyección", 3, 10, 5)
        with col_b:
            wacc = st.slider("WACC (%)", 5.0, 18.0, 9.0, 0.25) / 100
            g = st.slider("Crecimiento a perpetuidad g (%)", 0.0, 4.0, 2.0, 0.25) / 100
            deuda_neta = st.number_input(f"Deuda neta (millones {moneda_fin})",
                                         value=float(round(deuda_neta_dato, 1)), step=100.0,
                                         help="Deuda financiera total menos caja. Negativa si hay más caja que deuda.")

        def dcf(fcf0, crec, n, wacc, g):
            t = np.arange(1, n + 1)
            flujos = fcf0 * (1 + crec) ** t
            vp_flujos = flujos / (1 + wacc) ** t
            vp_terminal = flujos[-1] * (1 + g) / (wacc - g) / (1 + wacc) ** n
            return flujos, vp_flujos, vp_terminal

        if fcf0 <= 0:
            st.warning("El flujo de caja libre es negativo o cero: un DCF simple no es confiable para esta empresa "
                       "(común en años de alta inversión). Ingrese un flujo normalizado para hacer el ejercicio.")
        elif not acciones:
            st.warning("No hay dato de acciones en circulación para esta empresa.")
        elif wacc <= g:
            st.error("El WACC debe ser mayor que g.")
        else:
            flujos, vp_flujos, vp_terminal = dcf(fcf0, crecimiento, anios, wacc, g)
            ev = vp_flujos.sum() + vp_terminal
            patrimonio = ev - deuda_neta
            precio_objetivo = patrimonio * 1e6 / acciones * fx
            potencial = precio_objetivo / precio - 1

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Valor empresa (EV)", num(ev, 0, f" M {moneda_fin}"))
            r2.metric("Valor patrimonio", num(patrimonio, 0, f" M {moneda_fin}"))
            r3.metric("Precio objetivo", num(precio_objetivo, 1, f" {moneda}"))
            r4.metric("Potencial", pct(potencial), delta=pct(potencial))
            st.caption(f"El valor terminal representa el {vp_terminal / ev:.0%} del EV. "
                       f"EV / FCF implícito: {ev / fcf0:.1f}x.")

            valorizacion = {"Método": "DCF", "Precio objetivo": num(precio_objetivo, 1, f" {moneda}"),
                            "Potencial": pct(potencial), "WACC": f"{wacc:.2%}", "g": f"{g:.2%}",
                            "Crecimiento flujo": f"{crecimiento:.1%}"}

            col_t, col_s = st.columns(2)
            with col_t:
                st.subheader("Flujos proyectados")
                st.dataframe(pd.DataFrame({
                    "Año": np.arange(1, anios + 1),
                    f"Flujo (M {moneda_fin})": flujos.round(1),
                    f"Valor presente (M {moneda_fin})": vp_flujos.round(1),
                }), hide_index=True)
            with col_s:
                st.subheader("Sensibilidad del precio objetivo")
                waccs = [wacc + d for d in (-0.01, -0.005, 0, 0.005, 0.01)]
                gs = [g + d for d in (-0.005, 0, 0.005)]
                sens = {}
                for gi in gs:
                    columna = []
                    for wi in waccs:
                        if wi <= gi:
                            columna.append(np.nan)
                            continue
                        _, vpf, vpt = dcf(fcf0, crecimiento, anios, wi, gi)
                        columna.append((vpf.sum() + vpt - deuda_neta) * 1e6 / acciones * fx)
                    sens[f"g {gi:.2%}"] = columna
                st.dataframe(pd.DataFrame(sens, index=[f"WACC {w:.2%}" for w in waccs]).style.format("{:,.1f}"))

# ---------------------------- Bancos ----------------------------------------
if tipo == "banco":
    with tabs["Valorización bancaria (P/B)"]:
        st.markdown(
            "Los bancos no se valorizan por flujo de caja libre (la deuda es su materia prima). "
            "Se usa el **Precio / Valor libro justificado**:  \n"
            "**P/B justo = (ROE − g) / (Ke − g)**, donde Ke es el costo del patrimonio."
        )
        valor_libro = info.get("bookValue")
        roe_dato = info.get("returnOnEquity")

        if not es_num(valor_libro) or valor_libro <= 0:
            st.warning("No hay dato de valor libro por acción para esta entidad.")
        else:
            valor_libro_local = valor_libro * fx
            col_a, col_b = st.columns(2)
            with col_a:
                roe = st.slider("ROE sostenible (%)", 0.0, 35.0,
                                float(round((roe_dato if es_num(roe_dato) else 0.15) * 100, 1)), 0.5) / 100
                ke = st.slider("Costo del patrimonio Ke (%)", 5.0, 20.0, 11.0, 0.25) / 100
            with col_b:
                g = st.slider("Crecimiento de largo plazo g (%)", 0.0, 6.0, 3.0, 0.25) / 100
                st.metric("Valor libro por acción", num(valor_libro_local, 2, f" {moneda}"))

            if ke <= g:
                st.error("Ke debe ser mayor que g.")
            else:
                pb_justo = (roe - g) / (ke - g)
                pb_actual = precio / valor_libro_local
                precio_objetivo = pb_justo * valor_libro_local
                potencial = precio_objetivo / precio - 1

                r1, r2, r3, r4 = st.columns(4)
                r1.metric("P/B actual", num(pb_actual, 2, "x"))
                r2.metric("P/B justo", num(pb_justo, 2, "x"))
                r3.metric("Precio objetivo", num(precio_objetivo, 1, f" {moneda}"))
                r4.metric("Potencial", pct(potencial), delta=pct(potencial))

                roe_implicito = g + pb_actual * (ke - g)
                st.caption(f"ROE implícito en el precio actual: {roe_implicito:.1%} "
                           f"(lo que el mercado espera que el banco rente de forma sostenida).")
                if roe > ke:
                    st.success("ROE > Ke: la entidad crea valor, por eso merece transar sobre su valor libro (P/B > 1).")
                else:
                    st.info("ROE < Ke: la entidad no cubre su costo de capital, por eso su P/B justo es menor a 1.")

                valorizacion = {"Método": "P/B justificado", "P/B justo": num(pb_justo, 2, "x"),
                                "P/B actual": num(pb_actual, 2, "x"),
                                "Precio objetivo": num(precio_objetivo, 1, f" {moneda}"),
                                "Potencial": pct(potencial), "ROE": f"{roe:.1%}", "Ke": f"{ke:.2%}"}

                st.subheader("Sensibilidad del precio objetivo")
                roes = [roe + d for d in (-0.04, -0.02, 0, 0.02, 0.04)]
                kes = [ke + d for d in (-0.01, 0, 0.01)]
                sens = {f"Ke {k:.2%}": [((r - g) / (k - g)) * valor_libro_local if k > g else np.nan for r in roes]
                        for k in kes}
                st.dataframe(pd.DataFrame(sens, index=[f"ROE {r:.1%}" for r in roes]).style.format("{:,.1f}"))

# ---------------------------- Comparables -----------------------------------
if "Comparables del sector" in tabs:
    with tabs["Comparables del sector"]:
        st.markdown(f"Múltiplos de todas las empresas de **{categoria}**.")
        if st.toggle("Cargar comparables (tarda unos segundos la primera vez)", value=False):
            filas = []
            barra = st.progress(0.0)
            pares = ACTIVOS[categoria]
            for i, (nom, tk) in enumerate(pares.items()):
                tk = resolver(tk)
                inf = ficha(tk)
                s = historial(tk, "1y")
                barra.progress((i + 1) / len(pares))
                if s.empty:
                    continue
                p = float(s.iloc[-1])
                fx_par = tipo_de_cambio(inf.get("financialCurrency", inf.get("currency")), inf.get("currency")) or 1.0
                vl = inf.get("bookValue")
                filas.append({
                    "Empresa": nom,
                    "Retorno 1 año": s.iloc[-1] / s.iloc[0] - 1,
                    "PER": inf.get("trailingPE"),
                    "P/B": p / (vl * fx_par) if es_num(vl) and vl > 0 else None,
                    "ROE": inf.get("returnOnEquity"),
                    "Dividend yield": dividendos_12m(tk) / p if p else None,
                    "Margen EBITDA": inf.get("ebitdaMargins") if tipo == "empresa" else None,
                    "Market cap (miles de millones)": (inf.get("marketCap") or np.nan) / 1e9,
                })
            barra.empty()
            df_comp = pd.DataFrame(filas).set_index("Empresa")
            if tipo == "banco":
                df_comp = df_comp.drop(columns="Margen EBITDA")
            df_comp = df_comp.apply(pd.to_numeric, errors="coerce")

            formatos = {c: (lambda v: pct(v, signo=False)) for c in ("ROE", "Dividend yield", "Margen EBITDA") if c in df_comp}
            formatos.update({"Retorno 1 año": lambda v: pct(v), "PER": lambda v: num(v, 1, "x"),
                             "P/B": lambda v: num(v, 2, "x"), "Market cap (miles de millones)": lambda v: num(v, 1)})
            st.dataframe(df_comp.style.format(formatos)
                         .apply(lambda fila: ["font-weight: bold; color: #00E5FF" if fila.name == nombre else ""
                                              for _ in fila], axis=1))

            medianas = df_comp.median(numeric_only=True)
            if nombre in df_comp.index:
                actual = df_comp.loc[nombre]
                c1, c2, c3 = st.columns(3)
                for col, metrica in zip((c1, c2, c3), ("PER", "P/B", "Dividend yield")):
                    if es_num(actual.get(metrica)) and es_num(medianas.get(metrica)) and medianas[metrica] != 0:
                        dif = actual[metrica] / medianas[metrica] - 1
                        col.metric(f"{metrica} vs mediana del sector", pct(dif),
                                   help="Positivo: más caro (PER, P/B) o mejor dividendo que la mediana.")
            if "ROE" in df_comp and "P/B" in df_comp:
                datos_disp = df_comp[["ROE", "P/B"]].dropna()
                if len(datos_disp) >= 2:
                    fig = px.scatter(datos_disp.reset_index(), x="ROE", y="P/B", text="Empresa",
                                     title="ROE vs P/B: mayor rentabilidad debería justificar mayor múltiplo")
                    fig.update_traces(textposition="top center")
                    fig.update_layout(xaxis_tickformat=".0%")
                    st.plotly_chart(fig)

# ---------------------------- Dividendos ------------------------------------
if "Dividendos" in tabs:
    with tabs["Dividendos"]:
        div = dividendos(ticker)
        if div.empty:
            st.info("Esta empresa no registra dividendos en Yahoo Finance.")
        else:
            por_anio = div.groupby(div.index.year).sum()
            por_anio = por_anio[por_anio.index >= pd.Timestamp.now().year - 10]
            fig = px.bar(x=por_anio.index.astype(str), y=por_anio.values,
                         title=f"Dividendos por acción por año ({moneda})")
            fig.update_layout(xaxis_title=None, yaxis_title=moneda)
            st.plotly_chart(fig)
            c1, c2, c3 = st.columns(3)
            c1.metric("Dividendos últimos 12 meses", num(dividendos_12m(ticker), 2, f" {moneda}"))
            c2.metric("Dividend yield (12m)", pct(dividendos_12m(ticker) / precio, signo=False))
            c3.metric("Último pago", f"{div.index[-1]:%d-%m-%Y}")
            st.caption("En Chile las sociedades anónimas abiertas deben repartir al menos 30% de la utilidad, "
                       "por eso muchas acciones del IPSA tienen dividend yield alto.")

# ---------------------------- Comparar --------------------------------------
with tabs["Comparar y correlaciones"]:
    opciones = [n for n in TODOS if n != nombre]
    por_defecto = [n for n in COMPARAR_POR_DEFECTO.get(categoria, []) if n != nombre and n in TODOS]
    elegidos = st.multiselect("Comparar con", opciones, default=por_defecto)

    series = {nombre: precios}
    for otro in elegidos:
        s = historial(TODOS[otro], periodo)
        if not s.empty:
            series[otro] = s
        else:
            st.warning(f"Sin datos para {otro}.")

    if len(series) < 2:
        st.info("Elija al menos un activo para comparar.")
    else:
        df = pd.concat(series, axis=1).ffill().dropna()
        base100 = df / df.iloc[0] * 100
        st.plotly_chart(grafico_linea(base100, "Desempeño relativo (base 100)", "Base 100"))

        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Rentabilidad y riesgo")
            resumen = pd.DataFrame({n: metricas_riesgo(df[n]) for n in df.columns}).T
            st.dataframe(resumen.style.format(lambda v: pct(v)))
        with col_b:
            st.subheader("Correlación de retornos diarios")
            corr = df.pct_change().dropna().corr()
            fig = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu", zmin=-1, zmax=1, aspect="auto")
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig)

        retornos = df.pct_change().dropna()
        if len(retornos) > 60:
            otro = st.selectbox("Correlación móvil de 60 días contra", [c for c in df.columns if c != nombre])
            corr_movil = retornos[nombre].rolling(60).corr(retornos[otro]).dropna()
            fig = grafico_linea(corr_movil.rename(f"{nombre} vs {otro}"),
                                "Correlación móvil (60 días): cómo cambia la relación en el tiempo", "Correlación")
            fig.add_hline(y=0, line_dash="dot")
            st.plotly_chart(fig)
        st.caption("Correlación cercana a 1: se mueven juntos. Cercana a −1: en sentido contrario. "
                   "Cercana a 0: sin relación.")

# ---------------------------- Tesis con IA ----------------------------------
if "Tesis con IA" in tabs:
    with tabs["Tesis con IA"]:
        if not OLLAMA:
            st.info("Esta función usa Llama 3 corriendo localmente con Ollama, por lo que no está disponible "
                    "en la versión web. Clone el repositorio y ejecútelo en su equipo para usarla.")
        elif not valorizacion:
            st.warning("Complete primero la valorización con supuestos válidos.")
        elif st.button("Generar tesis de inversión"):
            datos = "\n".join(f"- {k}: {v}" for k, v in valorizacion.items())
            prompt = f"""Actúa como analista senior de equity research. Empresa: {nombre} ({ticker}),
sector {info.get('sector', 'N/A')}. Precio actual: {precio:,.2f} {moneda}.
Retorno 1 año: {pct(riesgo['1 año'])}. Volatilidad anual: {pct(riesgo['Volatilidad anual'], signo=False)}.
PER: {num(info.get('trailingPE'), 1, 'x')}. ROE: {pct(info.get('returnOnEquity'), signo=False)}.
Resultado de la valorización:
{datos}

Redacta en español un reporte breve con: 1) tesis de inversión, 2) supuestos clave y drivers
(considera el contexto macro de Chile si aplica: cobre, dólar, tasas, China), 3) principales riesgos,
4) recomendación (comprar / mantener / vender) justificada."""
            with st.spinner("Generando tesis..."):
                try:
                    respuesta = ollama.chat(model="llama3", messages=[{"role": "user", "content": prompt}])
                    st.markdown(respuesta["message"]["content"])
                except Exception:
                    st.info("No se pudo conectar con Ollama. Verifique que esté corriendo (`ollama serve`) "
                            "y que tenga el modelo (`ollama pull llama3`).")
