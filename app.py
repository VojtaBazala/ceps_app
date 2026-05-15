import streamlit as st
from zeep import Client
from zeep.transports import Transport
from lxml import etree
import requests
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── KONFIGURACE ────────────────────────────────────
st.set_page_config(
    page_title="ČEPS Dispečink",
    page_icon="⚡",
    layout="wide"
)

WSDL = "https://vip-prod-service-00-azapp.azurewebsites.net/_layouts/cepsdata.asmx?WSDL"
NS   = "https://www.ceps.cz/CepsData/StructuredData/1.0"

# ── SOAP KLIENT (cachovaný) ────────────────────────
@st.cache_resource
def get_client():
    session = requests.Session()
    return Client(WSDL, transport=Transport(session=session))

# ── PARSOVÁNÍ XML ──────────────────────────────────
def xml_na_df(result):
    items = result.findall(f"{{{NS}}}data/{{{NS}}}item")
    if not items:
        items = result.findall("data/item")
    radky = []
    for item in items:
        radek = {"cas": item.get("date")}
        for k, v in item.attrib.items():
            if k != "date":
                try:
                    radek[k] = float(v)
                except (ValueError, TypeError):
                    radek[k] = 0.0
        radky.append(radek)
    if not radky:
        return pd.DataFrame()
    df = pd.DataFrame(radky)
    df["cas"] = pd.to_datetime(df["cas"], utc=True).dt.tz_convert("Europe/Prague")
    return df

def nazvy_serii(result):
    serie_els = result.findall(f"{{{NS}}}series/{{{NS}}}serie")
    if not serie_els:
        serie_els = result.findall("series/serie")
    return {s.get("id"): s.get("name") for s in serie_els}

# ── STAŽENÍ DAT ────────────────────────────────────
@st.cache_data(ttl=60)
def stahni_data(date_from: datetime, date_to: datetime):
    client = get_client()
    vysledky = {}

    r = client.service.Frekvence(dateFrom=date_from, dateTo=date_to)
    vysledky["freq_df"]    = xml_na_df(r)

    r = client.service.AktivaceSVRvCR(dateFrom=date_from, dateTo=date_to)
    vysledky["svr_df"]     = xml_na_df(r)
    vysledky["svr_nazvy"]  = nazvy_serii(r)

    r = client.service.AktualniCenaRE(dateFrom=date_from, dateTo=date_to)
    vysledky["cena_df"]    = xml_na_df(r)
    vysledky["cena_nazvy"] = nazvy_serii(r)

    return vysledky

# ── SIDEBAR ────────────────────────────────────────
with st.sidebar:
    st.title("⚡ ČEPS Dispečink")
    st.caption("Oficiální SOAP API · cepsdata.asmx")
    st.divider()

    obdobi = st.selectbox("Období", [
        "Dnešní den",
        "Posledních 24 hodin",
        "Posledních 3 dny",
        "Posledních 7 dní",
    ])

    st.divider()
    st.markdown("**Co zobrazit:**")
    zobraz_freq = st.checkbox("Frekvence sítě",   value=True)
    zobraz_svr  = st.checkbox("Aktivace SVR",      value=True)
    zobraz_cena = st.checkbox("Aktuální cena RE",  value=True)

    st.divider()
    nacist = st.button("🔄 Načíst / Obnovit", use_container_width=True)
    st.caption(f"Data se cachují 60 s")

# ── DATOVÝ ROZSAH ──────────────────────────────────
now = datetime.now()

if   obdobi == "Dnešní den":
    date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
elif obdobi == "Posledních 24 hodin":
    date_from = now - timedelta(hours=24)
elif obdobi == "Posledních 3 dny":
    date_from = now - timedelta(days=3)
else:
    date_from = now - timedelta(days=7)

date_to = now

# ── HLAVNÍ OBSAH ───────────────────────────────────
st.title("⚡ ČEPS – Dispečink live")
st.caption(f"📅 {date_from.strftime('%d.%m.%Y %H:%M')} – {date_to.strftime('%d.%m.%Y %H:%M')}")

if not nacist:
    st.info("👈 Zvolte parametry a klikněte **Načíst / Obnovit**.")
    st.stop()

# Stažení
with st.spinner("Stahuji data z ČEPS SOAP API..."):
    try:
        data = stahni_data(date_from, date_to)
    except Exception as e:
        st.error(f"❌ Chyba při stahování dat: {e}")
        st.stop()

st.caption(f"✅ Aktualizováno: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

# ── METRIKY ────────────────────────────────────────
df_freq = data["freq_df"]
df_svr  = data["svr_df"]
df_cena = data["cena_df"]

if not df_freq.empty:
    last_freq = df_freq["value1"].iloc[-1]
    prev_freq = df_freq["value1"].iloc[-2] if len(df_freq) > 1 else last_freq
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("⚡ Frekvence", f"{last_freq:.3f} Hz",
                f"{last_freq - prev_freq:+.3f} Hz")

if not df_svr.empty and data["svr_nazvy"]:
    nazvy = data["svr_nazvy"]
    cols  = st.columns(len(nazvy))
    for i, (vid, vname) in enumerate(nazvy.items()):
        if vid in df_svr.columns:
            last = df_svr[vid].iloc[-1]
            cols[i].metric(vname, f"{last:+.2f} MW")

if not df_cena.empty and data["cena_nazvy"]:
    nazvy = data["cena_nazvy"]
    cols  = st.columns(len(nazvy))
    for i, (vid, vname) in enumerate(nazvy.items()):
        if vid in df_cena.columns:
            last = df_cena[vid].iloc[-1]
            cols[i].metric(vname, f"{last:.2f} EUR/MWh")

st.divider()

# ── BARVY ──────────────────────────────────────────
BARVY_SVR  = {"value1": "#bf2837", "value2": "#b1b2b7",
              "value3": "#fdc82f", "value4": "#13b8f0", "value7": "#4baf4f"}
BARVY_CENA = {"value1": "#00e676", "value2": "#ffd740",
              "value3": "#13b8f0", "value4": "#4baf4f"}

PLOT_BG = "#0f1628"
PAPER_BG = "#0a0e1a"
GRID_COLOR = "#1e2d50"
FONT_COLOR = "#cdd8f0"

def base_layout(title):
    return dict(
        title=dict(text=title, font=dict(color="#00c8ff", size=14)),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(color=FONT_COLOR, family="monospace", size=11),
        hovermode="x unified",
        legend=dict(bgcolor=PLOT_BG, bordercolor=GRID_COLOR),
        xaxis=dict(gridcolor=GRID_COLOR, showgrid=True),
        yaxis=dict(gridcolor=GRID_COLOR, showgrid=True),
        margin=dict(l=60, r=20, t=50, b=40),
    )

# ── GRAF: FREKVENCE ────────────────────────────────
if zobraz_freq and not df_freq.empty:
    st.subheader("📡 Frekvence sítě")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_freq["cas"], y=df_freq["value1"],
        name="Frekvence [Hz]",
        line=dict(color="#00c8ff", width=1.5),
        hovertemplate="%{x|%H:%M}<br><b>%{y:.3f} Hz</b>",
    ))
    fig.add_hline(y=50.0, line_dash="dash",
                  line_color="rgba(255,255,255,0.2)",
                  annotation_text="50 Hz",
                  annotation_font_color="#8899bb")
    fig.update_layout(**base_layout("Frekvence sítě [Hz]"))
    fig.update_yaxes(tickformat=".3f")
    st.plotly_chart(fig, use_container_width=True)

# ── GRAF: AKTIVACE SVR ─────────────────────────────
if zobraz_svr and not df_svr.empty:
    st.subheader("📊 Aktivace SVR v ČR")
    fig2 = go.Figure()
    for vid, vname in data["svr_nazvy"].items():
        if vid in df_svr.columns:
            fig2.add_trace(go.Bar(
                x=df_svr["cas"], y=df_svr[vid],
                name=vname,
                marker_color=BARVY_SVR.get(vid, "#888"),
                hovertemplate=f"{vname}<br>%{{x|%H:%M}}<br><b>%{{y:+.2f}} MW</b>",
            ))
    fig2.update_layout(**base_layout("Aktivace SVR v ČR [MW]"))
    fig2.update_layout(barmode="relative")
    st.plotly_chart(fig2, use_container_width=True)

# ── GRAF: CENA RE ──────────────────────────────────
if zobraz_cena and not df_cena.empty:
    st.subheader("💶 Aktuální cena RE")
    fig3 = go.Figure()
    for vid, vname in data["cena_nazvy"].items():
        if vid in df_cena.columns:
            fig3.add_trace(go.Scatter(
                x=df_cena["cas"], y=df_cena[vid],
                name=vname,
                line=dict(color=BARVY_CENA.get(vid, "#888"), width=1.5),
                hovertemplate=f"{vname}<br>%{{x|%H:%M}}<br><b>%{{y:.2f}} EUR/MWh</b>",
            ))
    fig3.update_layout(**base_layout("Aktuální cena RE [EUR/MWh]"))
    st.plotly_chart(fig3, use_container_width=True)

# ── PATIČKA ────────────────────────────────────────
st.divider()
st.caption("Data: ČEPS, a.s. – Oficiální SOAP API (cepsdata.asmx) · Bez omezení IP")
