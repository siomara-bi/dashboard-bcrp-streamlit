import io
import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
import requests

st.set_page_config(
    page_title="Dashboard BCRP - Indicadores Macroeconómicos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
FACT_PATH = DATA_DIR / "bcrp_data_limpia.csv"
META_PATH = DATA_DIR / "bcrp_series_metadata.csv"

MONTHS = {"Ene":1,"Feb":2,"Mar":3,"Abr":4,"May":5,"Jun":6,"Jul":7,"Ago":8,"Sep":9,"Oct":10,"Nov":11,"Dic":12}

@st.cache_data(show_spinner=False)
def load_local_data():
    fact = pd.read_csv(FACT_PATH, parse_dates=["Periodo", "Fecha_Carga"])
    meta = pd.read_csv(META_PATH)
    return fact, meta

def _period_to_date(periodo: str):
    periodo = periodo.strip()
    mon = periodo[:3]
    yy = int(periodo[3:])
    year = 2000 + yy if yy <= 49 else 1900 + yy
    return pd.Timestamp(year=year, month=MONTHS[mon], day=1)

@st.cache_data(show_spinner=True, ttl=60*60*6)
def fetch_bcrp_from_api(meta: pd.DataFrame, start="2020-1", end="2026-6"):
    """Actualiza datos desde la API oficial del BCRP. Si falla, retorna None."""
    frames = []
    for _, row in meta.iterrows():
        code = row["CodigoSerie"]
        url = f"https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{code}/json/{start}/{end}/esp"
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            js = r.json()
            periods = js.get("periods", [])
            tmp = []
            for p in periods:
                vals = p.get("values", [])
                if not vals:
                    continue
                try:
                    value = float(vals[0])
                except Exception:
                    continue
                tmp.append({
                    "Periodo": _period_to_date(p["name"]),
                    "CodigoSerie": code,
                    "NombreIndicador": row["NombreIndicador"],
                    "NombreCorto": row["NombreCorto"],
                    "Categoria": row["Categoria"],
                    "Unidad": row["Unidad"],
                    "Valor": value,
                    "Fuente_URL": row["Fuente_URL"],
                    "Fecha_Carga": pd.Timestamp.today().normalize(),
                })
            if tmp:
                frames.append(pd.DataFrame(tmp))
        except Exception:
            return None
    if not frames:
        return None
    fact = pd.concat(frames, ignore_index=True).sort_values(["CodigoSerie","Periodo"])
    fact["Anio"] = fact["Periodo"].dt.year
    fact["MesNumero"] = fact["Periodo"].dt.month
    fact["MesNombre"] = fact["Periodo"].dt.month_name(locale=None)
    fact["Trimestre"] = "T" + fact["Periodo"].dt.quarter.astype(str)
    # métricas derivadas por indicador
    fact["Valor_Mes_Anterior"] = fact.groupby("CodigoSerie")["Valor"].shift(1)
    fact["Variacion_Mensual_Abs"] = fact["Valor"] - fact["Valor_Mes_Anterior"]
    fact["Variacion_Mensual_Pct"] = (fact["Valor"] / fact["Valor_Mes_Anterior"] - 1) * 100
    fact["Valor_Anio_Anterior"] = fact.groupby("CodigoSerie")["Valor"].shift(12)
    fact["Variacion_Interanual_Abs"] = fact["Valor"] - fact["Valor_Anio_Anterior"]
    fact["Variacion_Interanual_Pct"] = (fact["Valor"] / fact["Valor_Anio_Anterior"] - 1) * 100
    return fact

def fmt_value(v, unidad):
    if pd.isna(v):
        return "—"
    if "%" in str(unidad):
        return f"{v:.2f}%"
    if "S/" in str(unidad):
        return f"S/ {v:.3f}"
    return f"{v:,.2f}"

def fmt_delta(v, unidad):
    if pd.isna(v):
        return None
    if "%" in str(unidad):
        return f"{v:+.2f} p.p. vs mes anterior"
    return f"{v:+.2f} vs mes anterior"

fact_local, meta = load_local_data()
with st.sidebar:
    st.title("⚙️ Filtros")
    refresh = st.toggle("Actualizar desde API BCRP", value=False, help="Requiere internet. Si falla, se usa la base local limpia incluida.")

fact = fact_local.copy()
if refresh:
    fresh = fetch_bcrp_from_api(meta)
    if fresh is not None:
        fact = fresh
        st.sidebar.success("Datos actualizados desde API BCRP")
    else:
        st.sidebar.warning("No se pudo conectar a BCRP. Se usa base local incluida.")

fact["Periodo"] = pd.to_datetime(fact["Periodo"])
min_date, max_date = fact["Periodo"].min(), fact["Periodo"].max()

with st.sidebar:
    indicadores = st.multiselect(
        "Indicadores",
        options=meta["NombreIndicador"].tolist(),
        default=meta["NombreIndicador"].tolist(),
    )
    years = sorted(fact["Anio"].dropna().unique().tolist())
    year_range = st.slider("Rango de años", int(min(years)), int(max(years)), (2020, int(max(years))))
    mostrar_tabla = st.checkbox("Mostrar tabla limpia", value=False)

filtered = fact[
    fact["NombreIndicador"].isin(indicadores)
    & (fact["Anio"].between(year_range[0], year_range[1]))
].copy()

st.title("Dashboard BCRP: Indicadores Macroeconómicos del Perú")
st.caption("Versión publicable en Streamlit basada en datos mensuales de BCRPData. Incluye filtros, KPIs, evolución histórica, variaciones y tabla limpia descargable.")

latest = filtered.sort_values("Periodo").groupby("CodigoSerie", as_index=False).tail(1)
cols = st.columns(max(1, len(latest)))
for col, (_, r) in zip(cols, latest.iterrows()):
    col.metric(
        label=r["NombreCorto"],
        value=fmt_value(r["Valor"], r["Unidad"]),
        delta=fmt_delta(r.get("Variacion_Mensual_Abs"), r["Unidad"]),
    )
    col.caption(f"Último dato: {r['Periodo']:%b %Y} · {r['Unidad']}")

st.divider()

left, right = st.columns([2, 1])
with left:
    st.subheader("Evolución mensual")
    fig = px.line(
        filtered,
        x="Periodo", y="Valor", color="NombreCorto",
        markers=True,
        labels={"Valor":"Valor", "Periodo":"Periodo", "NombreCorto":"Indicador"},
        title="Serie histórica por indicador"
    )
    fig.update_layout(legend_orientation="h", legend_y=-0.25, height=520)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Último dato por indicador")
    latest_view = latest[["NombreCorto","Periodo","Valor","Unidad","Variacion_Mensual_Abs","Variacion_Interanual_Pct"]].copy()
    latest_view["Periodo"] = latest_view["Periodo"].dt.strftime("%Y-%m")
    st.dataframe(latest_view, hide_index=True, use_container_width=True)

st.subheader("Variación interanual calculada sobre el valor de la serie")
var_df = filtered.dropna(subset=["Variacion_Interanual_Pct"]).copy()
fig2 = px.bar(
    var_df,
    x="Periodo", y="Variacion_Interanual_Pct", color="NombreCorto",
    barmode="group",
    labels={"Variacion_Interanual_Pct":"Var. interanual calculada (%)", "Periodo":"Periodo"},
)
fig2.update_layout(height=420, legend_orientation="h", legend_y=-0.25)
st.plotly_chart(fig2, use_container_width=True)

st.subheader("Lectura rápida")
if not latest.empty:
    infl = latest[latest["CodigoSerie"] == "PN01273PM"]
    tasa = latest[latest["CodigoSerie"] == "PD04722MM"]
    tc = latest[latest["CodigoSerie"] == "PN01207PM"]
    pbi = latest[latest["CodigoSerie"] == "PN01770AM"]
    bullets = []
    if not infl.empty:
        bullets.append(f"La inflación anual disponible se ubica en **{infl.iloc[0]['Valor']:.2f}%** al último mes cargado.")
    if not tasa.empty:
        bullets.append(f"La tasa de referencia se mantiene en **{tasa.iloc[0]['Valor']:.2f}%** en el último registro.")
    if not tc.empty:
        bullets.append(f"El tipo de cambio promedio interbancario registra **S/ {tc.iloc[0]['Valor']:.3f} por US$**.")
    if not pbi.empty:
        bullets.append(f"El índice mensual de PBI alcanza **{pbi.iloc[0]['Valor']:.1f}** en el último dato disponible.")
    st.markdown("\n".join(f"- {b}" for b in bullets))

if mostrar_tabla:
    st.subheader("Base limpia")
    st.dataframe(filtered.sort_values(["NombreIndicador","Periodo"]), use_container_width=True, hide_index=True)

csv_bytes = filtered.to_csv(index=False).encode("utf-8-sig")
st.download_button("⬇️ Descargar datos filtrados CSV", data=csv_bytes, file_name="bcrp_data_filtrada.csv", mime="text/csv")

with st.expander("Fuentes y notas metodológicas"):
    st.markdown("""
    - Fuente principal: BCRPData, Base de Datos de Estadísticas del Banco Central de Reserva del Perú.
    - La base local fue normalizada a formato largo: un registro por indicador y periodo mensual.
    - La variación interanual calculada usa el valor del mismo indicador doce meses atrás; en indicadores que ya están expresados como porcentaje, esta métrica debe leerse solo como apoyo comparativo.
    """)
    st.dataframe(meta[["CodigoSerie","NombreIndicador","Unidad","Fuente_URL"]], hide_index=True, use_container_width=True)
