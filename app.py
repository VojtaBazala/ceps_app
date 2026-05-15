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

st.markdown("""
<style>
  #MainMenu {visibility: hidden;}
  footer {visibility: hidden;}
  header {visibility: hidden;}
  .block-container { padding-top: 1.5rem; padding-bottom: 1rem; }

  .ceps-title {
    font-family: 'Courier New', monospace;
    font-size: 2rem;
    font-weight: 700;
    color: #00c8ff;
    letter-spacing: 4px;
    text-transform: uppercase;
    margin-bottom: 0.2rem;
  }

  .status-bar {
    font-size: 0.8rem;
    color: #8899bb;
    margin-bottom: 1rem;
    font-family: monospace;
  }
  .status-bar .ok   { color: #00e676; }
  .status-bar .warn { color: #ffd740; }

  .divider {
    border-top: 1px solid #1e2d50;
    margin: 0.8rem 0;
  }

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

  .val-big {
    font-family: 'Courier New', monospace;
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.1;
  }
  .val-big.freq { color: #00c8ff; }

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
    margin-top: 10px;
    margin-bottom: 2px;
  }

  .delta-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 0;
    border-bottom: 1px solid #1e2d50;
    font-family: 'Courier New', monospace;
  }
  .delta-row:last-child { border-bottom: none; }
  .delta-label { font-size: 0.7rem; color: #8899bb; letter-spacing: 1px; }
  .delta-val   { font-size: 1rem; font-weight: 700; }
  .delta-val.pos  { color: #ff3d57; }
  .delta-val.neg  { color: #00e676; }
  .delta-val.zero { color: #8899bb; }

  .freq-status {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 3px;
    font-size: 0.7rem;
    font-family: 'Courier New', monospace;
    letter-spacing: 1px;
    margin-top: 4px;
    margin-bottom: 8px;
  }
  .freq-ok   { background: rgba(0,230,118,0.15); color: #00e676; }
  .freq-warn { background: rgba(255,215,64,0.15); color: #ffd740; }
  .freq-crit { background: rgba(255,61,87,0.15);  color: #ff3d57; }
</style>
""", unsafe_allow_html=True)

WSDL = "https://vip-prod-service-00-azapp.azurewebsites.net/_layouts/cepsdata.asmx?WSDL"
NS   = "https://www.ceps.cz/CepsData/StructuredData/1.0"

# ── SESSION STATE ──────────────────────────────────
if "auto_refresh"     not in st.session_state: st.session_state.auto_refresh     = False
if "countdown"        not in st.session_state: st.session_state.countdown        = 60
if "last_update"      not in st.session_state: st.session_state.last_update      = None
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

# ── VÝPOČET DELT ───────────────────────────────────
def vypocti_delty(df: pd.DataFrame) -> dict:
    """
    Delta 1 minuty = (50 - f) / 0.2 / 60  [sekundy]
    Delta Nh       = součet posledních N*60 minutových delt
    """
    if df.empty or "value1" not in df.columns:
        return {"1h": None, "2h": None, "4h": None, "8h": None}

    # Minutová delta pro každý řádek
    df = df.copy()
    df["delta_min"] = (50.0 - df["value1"]) / 0.2 / 60.0

    delty = {}
    for hodiny, label in [(1, "1h"), (2, "2h"), (4, "4h"), (8, "8h")]:
        pocet_minut = hodiny * 60
        if len(df) >= pocet_minut:
            delty[label] = df["delta_min"].iloc[-pocet_minut:].sum()
        elif len(df) > 0:
            # Méně dat než požadujeme – spočítáme z toho co máme
            delty[label] = df["delta_min"].sum()
        else:
            delty[label] = None
    return delty

# ── STAŽENÍ DAT ────────────────────────────────────
@st.cache_data(ttl=55)
def stahni_data(date_from, date_to):
    client = get_client()
    # Pro deltu 8h potřebujeme aspoň 8h dat – stáhneme od půlnoci nebo 8h zpět
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

# ── DATOVÝ ROZSAH ──────────────────────────────────
now       = datetime.now()
# Stahujeme od půlnoci nebo max 8h zpět – co je dřívější
pulnoc    = now.replace(hour=0, minute=0, second=0, microsecond=0)
osm_h     = now - timedelta(hours=8)
date_from = min(pulnoc, osm_h)
date_to   = now

# ── HLAVIČKA ───────────────────────────────────────
st.markdown('<div class="ceps-title">⚡ ČEPS online</div>', unsafe_allow_html=True)

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

df_freq   = data["freq_df"]
df_svr    = data["svr_df"]
df_cena   = data["cena_df"]
svr_nazvy = data["svr_nazvy"]
cena_nazvy = data["cena_nazvy"]

# Výpočet delt
delty = vypocti_delty(df_freq)

# ── TŘI SLOUPCE ────────────────────────────────────
col_freq, col_cena, col_svr = st.columns(3)

# ── FREKVENCE ──────────────────────────────────────
with col_freq:
    st.markdown('<div class="col-header freq">📡 Frekvence sítě</div>', unsafe_allow_html=True)
    if not df_freq.empty:
        last = df_freq["value1"].iloc[-1]
        cas  = df_freq["cas"].iloc[-1].strftime("%H:%M:%S")

        # Stav frekvence
        odchylka = abs(last - 50.0)
        if odchylka < 0.02:
            stav_cls, stav_txt = "freq-ok", "NORMÁLNÍ"
        elif odchylka < 0.1:
            stav_cls, stav_txt = "freq-warn", "ODCHYLKA"
        else:
            stav_cls, stav_txt = "freq-crit", "KRITICKÁ"

        st.markdown(f'<div class="val-big freq">{last:.3f} Hz</div>', unsafe_allow_html=True)
        st.markdown(f'<span class="freq-status {stav_cls}">{stav_txt}</span>', unsafe_allow_html=True)
        st.markdown(f'<div class="val-label">poslední měření: {cas}</div>', unsafe_allow_html=True)

        # Delty
        st.markdown('<div class="val-label" style="margin-top:14px">Kumulovaná odchylka síťového času</div>', unsafe_allow_html=True)

        delta_data = [
            ("Delta 1h",  delty.get("1h")),
            ("Delta 2h",  delty.get("2h")),
            ("Delta 4h",  delty.get("4h")),
            ("Delta 8h",  delty.get("8h")),
        ]

        html_delty = ""
        for label, val in delta_data:
            if val is None:
                val_str = "—"
                cls = "zero"
            else:
                if abs(val) < 0.01:
                    cls = "zero"
                elif val > 0:
                    cls = "pos"   # frekvence pod 50 Hz → ztráta času
                else:
                    cls = "neg"   # frekvence nad 50 Hz → zisk času
                val_str = f"{val:+.2f} s"
            html_delty += f"""
            <div class="delta-row">
              <span class="delta-label">{label}</span>
              <span class="delta-val {cls}">{val_str}</span>
            </div>"""

        st.markdown(html_delty, unsafe_allow_html=True)

        # Min/max/průměr
        st.markdown('<div class="val-label" style="margin-top:12px">Dnešní rozsah</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="val-small">'
            f'Min: {df_freq["value1"].min():.3f} Hz &nbsp;|&nbsp; '
            f'Max: {df_freq["value1"].max():.3f} Hz &nbsp;|&nbsp; '
            f'Ø: {df_freq["value1"].mean():.3f} Hz'
            f'</div>',
            unsafe_allow_html=True
        )
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
                color = "#00e676" if vid == "value1" else "#ffd740" if vid == "value2" else "#13b8f0"
                st.markdown(f'<div class="val-label">{vname}</div>', unsafe_allow_html=True)
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
        barvy = {"value1":"#bf2837","value2":"#b1b2b7",
                 "value3":"#fdc82f","value4":"#13b8f0","value7":"#4baf4f"}
        for vid, vname in svr_nazvy.items():
            if vid in df_svr.columns:
                last  = df_svr[vid].iloc[-1]
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

if not df_freq.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_freq["cas"], y=df_freq["value1"],
        name="Hz", line=dict(color="#00c8ff", width=1.2),
        hovertemplate="%{x|%H:%M}<br><b>%{y:.3f} Hz</b>",
    ))
    fig.add_hline(y=50.0, line_dash="dash", line_color="rgba(255,255,255,0.2)")
    fig.update_layout(**base_layout("Frekvence [Hz]", "#00c8ff"))
    fig.update_yaxes(tickformat=".3f")
    st.plotly_chart(fig, use_container_width=True)

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

# ── AUTO-REFRESH ───────────────────────────────────
if st.session_state.auto_refresh:
    time.sleep(1)
    st.session_state.countdown -= 1
    if st.session_state.countdown <= 0:
        st.cache_data.clear()
        st.session_state.last_update = datetime.now()
        st.session_state.countdown   = st.session_state.refresh_interval
    st.rerun()
