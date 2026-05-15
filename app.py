import streamlit as st
from zeep import Client
from zeep.transports import Transport
from lxml import etree
import requests
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
import time

# ── KONFIGURACE ────────────────────────────────────
st.set_page_config(
    page_title="ČEPS online",
    page_icon="⚡",
    layout="wide"
)

# Skryjeme výchozí Streamlit menu a patičku
st.markdown("""
<style>
  #MainMenu {visibility: hidden;}
  footer {visibility: hidden;}
  header {visibility: hidden;}
  .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

  /* Nadpis */
  .ceps-title {
    font-family: 'Courier New', monospace;
    font-size: 2rem;
    font-weight: 700;
    color: #00c8ff;
    letter-spacing: 4px;
    text-transform: uppercase;
    margin-bottom: 0.2rem;
  }

  /* Stavový řádek */
  .status-bar {
    font-size: 0.8rem;
    color: #8899bb;
    margin-bottom: 1rem;
    font-family: monospace;
  }
  .status-bar .ok   { color: #00e676; }
  .status-bar .warn { color: #ffd740; }

  /* Tlačítka refresh */
  div[data-testid="column"] button {
    width: 100%;
  }

  /* Oddělovač */
  .divider {
    border-top: 1px solid #1e2d50;
    margin: 0.8rem 0;
  }

  /* Sloupec – nadpis */
  .col-header {
    font-family: 'Courier New', monospace;
    font-size: 0.7rem;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #8899bb;
    border-bottom: 2px solid;
    padding-bottom: 6px;
    margin-bottom: 12px;
  }
  .col-header.freq  { border-color: #00c8ff; color: #00c8ff; }
  .col-header.cena  { border-color: #00e676; color: #00e676; }
  .col-header.svr   { border-color: #ffd740; color: #ffd740; }

  /* Hodnota – velká */
  .val-big {
    font-family: 'Courier New', monospace;
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.1;
  }
  .val-big.freq { color: #00c8ff; }
  .val-big.cena { color: #00e676; }
  .val-big.svr  { color: #ffd740; }

  /* Hodnota – malá */
  .val-small {
    font-family: 'Courier New', monospace;
    font-size: 0.85rem;
    color: #cdd8f0;
    margin: 4px 0;
  }
  .val-label {
    font-size: 0.65rem;
    color: #8899bb;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 8px;
  }

  /* Delta badge */
  .delta-up   { color: #00e676; font-size: 0.8rem; }
  .delta-down { color: #ff3d57; font-size: 0.8rem; }
  .delta-flat { color: #8899bb; font-size: 0.8rem; }

  /* Graf container */
  .graf-container {
    margin-top: 1rem;
    border-top: 1px solid #1e2d50;
    padding-top: 0.5rem;
  }
</style>
""", unsafe_allow_html=True)

WSDL = "https://vip-prod-service-00-azapp.azurewebsites.net/_layouts/cepsdata.asmx?WSDL"
NS   = "https://www.ceps.cz/CepsData/StructuredData/1.0"

# ── SESSION STATE ──────────────────────────────────
if "auto_refresh"    not in st.session_state: st.session_state.auto_refresh    = False
if "countdown"       not in st.session_state: st.session_state.countdown       = 60
if "last_update"     not in st.session_state: st.session_state.last_update     = None
if "refresh_interval" not in st.session_state: st.session_state.refresh_interval = 60

# ── SOAP KLIENT ────────────────────────────────────
@st.cache_resource
def get_client():
    session = requests.Session()
    return Client(WSDL, transport=Transport(session=session))

# ── PARSOVÁNÍ ──────────────────────────────────────
def xml_na_df(result):
    items = result.findall(f"{{{NS}}}data/{{{NS}}}item")
    if not items:
        items = result.findall("data/item")
    radky = []
    for item in items:
        radek = {"cas": item.get("date")}
        for k, v in item.attrib.items():
            if k != "date":
                try:    radek[k] = float(v)
                except: radek[k] = 0.0
        radky.append(radek)
    if not radky:
        return pd.DataFrame()
    df = pd.DataFrame(radky)
    df["cas"] = pd.to_datetime(df["cas"], utc=True).dt.tz_convert("Europe/Prague")
    return df

def nazvy_serii(result):
    els = result.findall(f"{{{NS}}}series/{{{NS}}}serie")
    if not els: els = result.findall("series/serie")
    return {s.get("id"): s.get("name") for s in els}

# ── STAŽENÍ DAT ────────────────────────────────────
@st.cache_data(ttl=55)
def stahni_data(date_from, date_to):
    client = get_client()
    r_freq = client.service.Frekvence(dateFrom=date_from, dateTo=date_to)
    r_svr  = client.service.AktivaceSVRvCR(dateFrom=date_from, dateTo=date_to)
    r_cena = client.service.AktualniCenaRE(dateFrom=date_from, dateTo=date_to)
    return {
        "freq_df":    xml_na_df(r_freq),
        "svr_df":     xml_na_df(r_svr),
        "svr_nazvy":  nazvy_serii(r_svr),
        "cena_df":    xml_na_df(r_cena),
        "cena_nazvy": nazvy_serii(r_cena),
    }

def delta_html(val, prev, fmt=".3f", unit=""):
    diff = val - prev
    if abs(diff) < 0.001:
        cls = "flat"; sign = "●"
    elif diff > 0:
        cls = "up"; sign = "▲"
    else:
        cls = "down"; sign = "▼"
    return f'<span class="delta-{cls}">{sign} {diff:+{fmt}} {unit}</span>'

# ── DATOVÝ ROZSAH ──────────────────────────────────
now       = datetime.now()
date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
date_to   = now

# ── HLAVIČKA ───────────────────────────────────────
st.markdown('<div class="ceps-title">⚡ ČEPS online</div>', unsafe_allow_html=True)

# Řádek s refresh tlačítky
c1, c2, c3, c4 = st.columns([2, 2, 2, 6])

with c1:
    if st.button("🔄 Obnovit data", use_container_width=True):
        st.cache_data.clear()
        st.session_state.last_update = datetime.now()
        st.session_state.countdown   = st.session_state.refresh_interval
        st.rerun()

with c2:
    if st.session_state.auto_refresh:
        if st.button("⏹ Zastavit auto", use_container_width=True):
            st.session_state.auto_refresh = False
            st.rerun()
    else:
        if st.button("▶ Spustit auto (60s)", use_container_width=True):
            st.session_state.auto_refresh = True
            st.session_state.countdown    = st.session_state.refresh_interval
            st.cache_data.clear()
            st.session_state.last_update  = datetime.now()
            st.rerun()

# Stavový řádek
last_str = st.session_state.last_update.strftime("%d.%m.%Y %H:%M:%S") \
           if st.session_state.last_update else "—"

if st.session_state.auto_refresh:
    status_html = (
        f'<div class="status-bar">'
        f'Poslední aktualizace: <span class="ok">{last_str}</span> &nbsp;|&nbsp; '
        f'Auto-refresh: <span class="ok">ZAP</span> &nbsp;|&nbsp; '
        f'Příští refresh za: <span class="warn">{st.session_state.countdown} s</span>'
        f'</div>'
    )
else:
    status_html = (
        f'<div class="status-bar">'
        f'Poslední aktualizace: <span class="ok">{last_str}</span> &nbsp;|&nbsp; '
        f'Auto-refresh: <span style="color:#ff3d57">VYP</span>'
        f'</div>'
    )
st.markdown(status_html, unsafe_allow_html=True)
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── DATA ───────────────────────────────────────────
with st.spinner("Načítám data..."):
    try:
        data = stahni_data(date_from, date_to)
        if st.session_state.last_update is None:
            st.session_state.last_update = datetime.now()
    except Exception as e:
        st.error(f"❌ Chyba: {e}")
        st.stop()

df_freq      = data["freq_df"]
df_svr       = data["svr_df"]
df_cena      = data["cena_df"]
svr_nazvy    = data["svr_nazvy"]
cena_nazvy   = data["cena_nazvy"]

# ── TŘI SLOUPCE ────────────────────────────────────
col_freq, col_cena, col_svr = st.columns(3)

# ── FREKVENCE ──────────────────────────────────────
with col_freq:
    st.markdown('<div class="col-header freq">📡 Frekvence sítě</div>', unsafe_allow_html=True)
    if not df_freq.empty:
        last = df_freq["value1"].iloc[-1]
        prev = df_freq["value1"].iloc[-2] if len(df_freq) > 1 else last
        cas  = df_freq["cas"].iloc[-1].strftime("%H:%M:%S")
        st.markdown(f'<div class="val-big freq">{last:.3f} Hz</div>', unsafe_allow_html=True)
        st.markdown(delta_html(last, prev, ".3f", "Hz"), unsafe_allow_html=True)
        st.markdown(f'<div class="val-label">poslední měření: {cas}</div>', unsafe_allow_html=True)

        # Mini statistiky
        st.markdown('<div class="val-label" style="margin-top:12px">Dnešní rozsah</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="val-small">Min: {df_freq["value1"].min():.3f} Hz</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="val-small">Max: {df_freq["value1"].max():.3f} Hz</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="val-small">Průměr: {df_freq["value1"].mean():.3f} Hz</div>', unsafe_allow_html=True)
    else:
        st.warning("Žádná data")

# ── CENA RE ────────────────────────────────────────
with col_cena:
    st.markdown('<div class="col-header cena">💶 Aktuální cena RE</div>', unsafe_allow_html=True)
    if not df_cena.empty:
        for vid, vname in cena_nazvy.items():
            if vid in df_cena.columns:
                last = df_cena[vid].iloc[-1]
                prev = df_cena[vid].iloc[-2] if len(df_cena) > 1 else last
                st.markdown(f'<div class="val-label">{vname}</div>', unsafe_allow_html=True)
                color = "#00e676" if vid == "value1" else "#ffd740" if vid == "value2" else "#13b8f0"
                st.markdown(
                    f'<div class="val-small" style="font-size:1.1rem;color:{color};font-weight:700">'
                    f'{last:.2f} EUR/MWh</div>',
                    unsafe_allow_html=True
                )
    else:
        st.warning("Žádná data")

# ── AKTIVACE SVR ───────────────────────────────────
with col_svr:
    st.markdown('<div class="col-header svr">📊 Aktivace SVR v ČR</div>', unsafe_allow_html=True)
    if not df_svr.empty:
        barvy = {"value1":"#bf2837","value2":"#b1b2b7","value3":"#fdc82f","value4":"#13b8f0","value7":"#4baf4f"}
        for vid, vname in svr_nazvy.items():
            if vid in df_svr.columns:
                last = df_svr[vid].iloc[-1]
                color = barvy.get(vid, "#cdd8f0")
                st.markdown(f'<div class="val-label">{vname}</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="val-small" style="font-size:1.1rem;color:{color};font-weight:700">'
                    f'{last:+.2f} MW</div>',
                    unsafe_allow_html=True
                )
    else:
        st.warning("Žádná data")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── GRAFY ──────────────────────────────────────────
PLOT_BG  = "#0f1628"
PAPER_BG = "#0a0e1a"
GRID_COL = "#1e2d50"
FONT_COL = "#cdd8f0"

def base_layout(title, color="#00c8ff"):
    return dict(
        title=dict(text=title, font=dict(color=color, size=13, family="Courier New")),
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=FONT_COL, family="Courier New", size=10),
        hovermode="x unified",
        legend=dict(bgcolor=PLOT_BG, bordercolor=GRID_COL, font=dict(size=10)),
        xaxis=dict(gridcolor=GRID_COL, showgrid=True),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True),
        margin=dict(l=50, r=10, t=40, b=30),
        height=220,
    )

# Graf frekvence
if not df_freq.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_freq["cas"], y=df_freq["value1"],
        name="Hz", line=dict(color="#00c8ff", width=1.2),
        hovertemplate="%{x|%H:%M}<br><b>%{y:.3f} Hz</b>",
    ))
    fig.add_hline(y=50.0, line_dash="dash",
                  line_color="rgba(255,255,255,0.2)")
    fig.update_layout(**base_layout("Frekvence [Hz]", "#00c8ff"))
    fig.update_yaxes(tickformat=".3f")
    st.plotly_chart(fig, use_container_width=True)

# Graf SVR
if not df_svr.empty:
    barvy = {"value1":"#bf2837","value2":"#b1b2b7",
             "value3":"#fdc82f","value4":"#13b8f0","value7":"#4baf4f"}
    fig2 = go.Figure()
    for vid, vname in svr_nazvy.items():
        if vid in df_svr.columns:
            fig2.add_trace(go.Bar(
                x=df_svr["cas"], y=df_svr[vid],
                name=vname, marker_color=barvy.get(vid, "#888"),
                hovertemplate=f"{vname}<br>%{{x|%H:%M}}<br><b>%{{y:+.2f}} MW</b>",
            ))
    fig2.update_layout(**base_layout("Aktivace SVR v ČR [MW]", "#ffd740"))
    fig2.update_layout(barmode="relative")
    st.plotly_chart(fig2, use_container_width=True)

# Graf cena RE
if not df_cena.empty:
    barvy_c = {"value1":"#00e676","value2":"#ffd740",
               "value3":"#13b8f0","value4":"#4baf4f"}
    fig3 = go.Figure()
    for vid, vname in cena_nazvy.items():
        if vid in df_cena.columns:
            fig3.add_trace(go.Scatter(
                x=df_cena["cas"], y=df_cena[vid],
                name=vname, line=dict(color=barvy_c.get(vid, "#888"), width=1.2),
                hovertemplate=f"{vname}<br>%{{x|%H:%M}}<br><b>%{{y:.2f}} EUR/MWh</b>",
            ))
    fig3.update_layout(**base_layout("Aktuální cena RE [EUR/MWh]", "#00e676"))
    st.plotly_chart(fig3, use_container_width=True)

# ── PATIČKA ────────────────────────────────────────
st.caption("Data: ČEPS, a.s. – Oficiální SOAP API (cepsdata.asmx)")

# ── AUTO-REFRESH LOGIKA ────────────────────────────
if st.session_state.auto_refresh:
    time.sleep(1)
    st.session_state.countdown -= 1
    if st.session_state.countdown <= 0:
        st.cache_data.clear()
        st.session_state.last_update = datetime.now()
        st.session_state.countdown   = st.session_state.refresh_interval
    st.rerun()
