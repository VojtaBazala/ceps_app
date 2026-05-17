import streamlit as st
from zeep import Client
from zeep.transports import Transport
import requests
from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
import time
import pytz
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navigation import show_nav

st.set_page_config(
    page_title="ČEPS online",
    page_icon="⚡",
    layout="wide"
)

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

if st.session_state.dark_mode:
    BG       = "#0a0e1a"
    BORDER   = "#1e2d50"
    TEXT     = "#cdd8f0"
    SUBTEXT  = "#8899bb"
    PLOT_BG  = "#0f1628"
    PAPER_BG = "#0a0e1a"
    GRID_COL = "#1e2d50"
    FONT_COL = "#cdd8f0"
    LEG_COL  = "#cdd8f0"
    BTN_TEMA = "☀️"
else:
    BG       = "#f5f7fa"
    BORDER   = "#dde3ef"
    TEXT     = "#1a2035"
    SUBTEXT  = "#6677aa"
    PLOT_BG  = "#ffffff"
    PAPER_BG = "#f5f7fa"
    GRID_COL = "#dde3ef"
    FONT_COL = "#1a2035"
    LEG_COL  = "#1a2035"
    BTN_TEMA = "🌙"

st.markdown(f"""
<style>
  #MainMenu {{visibility: hidden;}}
  footer {{visibility: hidden;}}
  header {{visibility: hidden;}}
  .block-container {{ padding-top: 1.2rem; padding-bottom: 1rem; background: {BG}; }}
  .stApp {{ background: {BG}; }}
  .ceps-title {{
    font-family: 'Courier New', monospace;
    font-size: 2rem; font-weight: 700; color: #00c8ff;
    letter-spacing: 4px; text-transform: uppercase; margin-bottom: 0.2rem;
  }}
  .status-bar {{ font-size: 0.8rem; color: {SUBTEXT}; margin-bottom: 0.8rem; font-family: monospace; }}
  .status-bar .ok   {{ color: #00e676; }}
  .status-bar .warn {{ color: #ffd740; }}
  .divider {{ border-top: 1px solid {BORDER}; margin: 0.8rem 0; }}
  .col-box {{ padding: 0 10px; height: 100%; }}
  .col-header {{
    font-family: 'Courier New', monospace; font-size: 0.7rem;
    letter-spacing: 3px; text-transform: uppercase;
    border-bottom: 2px solid; padding-bottom: 6px; margin-bottom: 14px;
  }}
  .col-header.freq {{ border-color: #00c8ff; color: #00c8ff; }}
  .col-header.cena {{ border-color: #00e676; color: #00e676; }}
  .col-header.svr  {{ border-color: #ffd740; color: #ffd740; }}
  .val-big {{ font-family: 'Courier New', monospace; font-size: 2rem; font-weight: 700; line-height: 1.1; color: #00c8ff; margin-bottom: 4px; }}
  .row-item {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 5px 0; border-bottom: 1px solid {BORDER}; font-family: 'Courier New', monospace;
  }}
  .row-item:last-child {{ border-bottom: none; }}
  .row-name  {{ font-size: 0.7rem; color: {SUBTEXT}; letter-spacing: 1px; }}
  .row-value {{ font-size: 0.95rem; font-weight: 700; }}
  .section-label {{
    font-size: 0.62rem; color: {SUBTEXT}; text-transform: uppercase;
    letter-spacing: 1px; margin-top: 12px; margin-bottom: 4px; font-family: 'Courier New', monospace;
  }}
  .freq-status {{
    display: inline-block; padding: 2px 10px; border-radius: 3px;
    font-size: 0.7rem; font-family: 'Courier New', monospace; letter-spacing: 1px; margin-bottom: 10px;
  }}
  .freq-ok   {{ background: rgba(0,230,118,0.15); color: #00e676; }}
  .freq-warn {{ background: rgba(255,215,64,0.15); color: #ffd740; }}
  .freq-crit {{ background: rgba(255,61,87,0.15);  color: #ff3d57; }}
  div[data-testid="stButton"] button {{
    background: transparent !important; border: 1px solid {BORDER} !important;
    color: {SUBTEXT} !important; font-size: 0.8rem !important;
    padding: 4px 10px !important; font-family: 'Courier New', monospace !important;
  }}
  div[data-testid="stButton"] button:hover {{ border-color: #00c8ff !important; color: #00c8ff !important; }}
</style>
""", unsafe_allow_html=True)

WSDL = "https://vip-prod-service-00-azapp.azurewebsites.net/_layouts/cepsdata.asmx?WSDL"
NS   = "https://www.ceps.cz/CepsData/StructuredData/1.0"
TZ   = pytz.timezone("Europe/Prague")

if "auto_refresh"     not in st.session_state: st.session_state.auto_refresh     = False
if "countdown"        not in st.session_state: st.session_state.countdown        = 60
if "last_update"      not in st.session_state: st.session_state.last_update      = None
if "refresh_interval" not in st.session_state: st.session_state.refresh_interval = 60

@st.cache_resource
def get_client():
    session = requests.Session()
    return Client(WSDL, transport=Transport(session=session))

def xml_na_df(result):
    items = result.findall(f"{{{NS}}}data/{{{NS}}}item")
    if not items: items = result.findall("data/item")
    radky = []
    for item in items:
        radek = {"cas": item.get("date")}
        for k, v in item.attrib.items():
            if k != "date":
                try:    radek[k] = float(v)
                except: radek[k] = 0.0
        radky.append(radek)
    if not radky: return pd.DataFrame()
    df = pd.DataFrame(radky)
    df["cas"] = pd.to_datetime(df["cas"], utc=True).dt.tz_convert("Europe/Prague")
    return df

def nazvy_serii(result):
    els = result.findall(f"{{{NS}}}series/{{{NS}}}serie")
    if not els: els = result.findall("series/serie")
    return {s.get("id"): s.get("name") for s in els}

def vypocti_delty(df):
    if df.empty or "value1" not in df.columns:
        return {"1 hod.": None, "2 hod.": None, "4 hod.": None, "8 hod.": None}
    df = df.copy()
    df["delta_min"] = (50.0 - df["value1"]) / 0.2 / 60.0
    delty = {}
    for hodiny, label in [(1,"1 hod."),(2,"2 hod."),(4,"4 hod."),(8,"8 hod.")]:
        pocet = hodiny * 60
        if len(df) >= pocet:   delty[label] = df["delta_min"].iloc[-pocet:].sum()
        elif len(df) > 0:      delty[label] = df["delta_min"].sum()
        else:                  delty[label] = None
    return delty

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

now_local = datetime.now(TZ)
now       = now_local.replace(tzinfo=None)
pulnoc    = now.replace(hour=0, minute=0, second=0, microsecond=0)
date_from = min(pulnoc, now - timedelta(hours=8))
date_to   = now

# ── HLAVIČKA ───────────────────────────────────────
header_l, header_r = st.columns([7, 3])
with header_l:
    st.markdown('<div class="ceps-title">⚡ ČEPS online</div>', unsafe_allow_html=True)
with header_r:
    nav_sp, nav_sel, nav_tema = st.columns([1, 3, 1])
    with nav_sel:
        show_nav("nav_ceps")
    with nav_tema:
        if st.button(BTN_TEMA, use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

c1, c2, _sp = st.columns([2, 2, 6])
with c1:
    if st.button("🔄 Obnovit", use_container_width=True):
        st.cache_data.clear()
        st.session_state.last_update = datetime.now(TZ)
        st.session_state.countdown   = st.session_state.refresh_interval
        st.rerun()
with c2:
    if st.session_state.auto_refresh:
        if st.button("⏹ Zastavit auto", use_container_width=True):
            st.session_state.auto_refresh = False
            st.rerun()
    else:
        if st.button("▶ Auto (60s)", use_container_width=True):
            st.session_state.auto_refresh = True
            st.session_state.countdown    = st.session_state.refresh_interval
            st.cache_data.clear()
            st.session_state.last_update  = datetime.now(TZ)
            st.rerun()

if st.session_state.last_update:
    lu = st.session_state.last_update
    if lu.tzinfo is None: lu = TZ.localize(lu)
    tz_label = "SELČ" if bool(lu.dst()) else "SEČ"
    last_str = lu.strftime("%d.%m.%Y %H:%M:%S") + f" {tz_label}"
else:
    last_str = "—"

if st.session_state.auto_refresh:
    status_html = (
        f'<div class="status-bar">Aktualizace: <span class="ok">{last_str}</span> &nbsp;|&nbsp; '
        f'Auto: <span class="ok">ZAP</span> &nbsp;|&nbsp; Za: <span class="warn">{st.session_state.countdown} s</span></div>'
    )
else:
    status_html = (
        f'<div class="status-bar">Aktualizace: <span class="ok">{last_str}</span> &nbsp;|&nbsp; '
        f'Auto: <span style="color:#ff3d57">VYP</span></div>'
    )
st.markdown(status_html, unsafe_allow_html=True)
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

with st.spinner("Načítám data..."):
    try:
        data = stahni_data(date_from, date_to)
        if st.session_state.last_update is None:
            st.session_state.last_update = datetime.now(TZ)
    except Exception as e:
        st.error(f"❌ Chyba: {e}")
        st.stop()

df_freq    = data["freq_df"]
df_svr     = data["svr_df"]
df_cena    = data["cena_df"]
svr_nazvy  = data["svr_nazvy"]
cena_nazvy = data["cena_nazvy"]
delty      = vypocti_delty(df_freq)

col_freq, _g1, col_cena, _g2, col_svr = st.columns([3, 0.2, 3, 0.2, 3])

with col_freq:
    st.markdown('<div class="col-box">', unsafe_allow_html=True)
    st.markdown('<div class="col-header freq">📡 Frekvence sítě</div>', unsafe_allow_html=True)
    if not df_freq.empty:
        last     = df_freq["value1"].iloc[-1]
        odchylka = abs(last - 50.0)
        if odchylka <= 0.05:   stav_cls, stav_txt = "freq-ok",  "NORMÁLNÍ"
        elif odchylka <= 0.13: stav_cls, stav_txt = "freq-warn", "VÝRAZNÁ"
        else:                  stav_cls, stav_txt = "freq-crit", "KRITICKÁ"
        st.markdown(f'<div class="val-big">{last:.3f} Hz</div>', unsafe_allow_html=True)
        st.markdown(f'<span class="freq-status {stav_cls}">{stav_txt}</span>', unsafe_allow_html=True)
        st.markdown('<div class="section-label">Změna kapacity 1 MW BESS za</div>', unsafe_allow_html=True)
        html_delty = ""
        for label, val in delty.items():
            if val is None: val_str, color = "—", SUBTEXT
            else:
                color   = "#00e676" if val > 0 else "#ff3d57" if val < 0 else SUBTEXT
                val_str = f"{val:+.4f} MWh"
            html_delty += f'<div class="row-item"><span class="row-name">{label}</span><span class="row-value" style="color:{color}">{val_str}</span></div>'
        st.markdown(html_delty, unsafe_allow_html=True)
        st.markdown(
            f'<div class="section-label" style="margin-top:14px">Dnešní rozsah</div>'
            f'<div style="font-family:\'Courier New\',monospace;font-size:0.75rem;color:{SUBTEXT};padding:4px 0;">'
            f'Min: <span style="color:{TEXT}">{df_freq["value1"].min():.3f} Hz</span>'
            f' &nbsp;|&nbsp; Max: <span style="color:{TEXT}">{df_freq["value1"].max():.3f} Hz</span>'
            f' &nbsp;|&nbsp; Ø: <span style="color:{TEXT}">{df_freq["value1"].mean():.3f} Hz</span></div>',
            unsafe_allow_html=True
        )
    else:
        st.warning("Žádná data")
    st.markdown('</div>', unsafe_allow_html=True)

with col_cena:
    st.markdown('<div class="col-box">', unsafe_allow_html=True)
    st.markdown('<div class="col-header cena">💶 Aktuální cena RE</div>', unsafe_allow_html=True)
    if not df_cena.empty:
        barvy_c = {"value1":"#00e676","value2":"#ffd740","value3":"#13b8f0","value4":"#4baf4f"}
        html_cena = ""
        for vid, vname in cena_nazvy.items():
            if vid in df_cena.columns:
                last  = df_cena[vid].iloc[-1]
                color = barvy_c.get(vid, TEXT)
                html_cena += f'<div class="row-item"><span class="row-name">{vname}</span><span class="row-value" style="color:{color}">{last:.2f} EUR/MWh</span></div>'
        st.markdown(html_cena, unsafe_allow_html=True)
    else:
        st.warning("Žádná data")
    st.markdown('</div>', unsafe_allow_html=True)

with col_svr:
    st.markdown('<div class="col-box">', unsafe_allow_html=True)
    st.markdown('<div class="col-header svr">📊 Aktivace SVR v ČR</div>', unsafe_allow_html=True)
    if not df_svr.empty:
        barvy = {"value1":"#bf2837","value2":"#b1b2b7","value3":"#fdc82f","value4":"#13b8f0","value7":"#4baf4f"}
        html_svr = ""
        for vid, vname in svr_nazvy.items():
            if vid in df_svr.columns:
                last  = df_svr[vid].iloc[-1]
                color = barvy.get(vid, TEXT)
                html_svr += f'<div class="row-item"><span class="row-name">{vname}</span><span class="row-value" style="color:{color}">{last:+.2f} MW</span></div>'
        st.markdown(html_svr, unsafe_allow_html=True)
    else:
        st.warning("Žádná data")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

def base_layout(title, color="#00c8ff"):
    return dict(
        title=dict(text=title, font=dict(color=color, size=13, family="Courier New")),
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=LEG_COL, family="Courier New", size=11),
        hovermode="x unified",
        legend=dict(bgcolor=PLOT_BG, bordercolor=BORDER, font=dict(size=11, color=LEG_COL)),
        xaxis=dict(gridcolor=GRID_COL, showgrid=True, color=LEG_COL),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True, color=LEG_COL),
        margin=dict(l=50, r=10, t=40, b=30), height=220,
    )

if not df_freq.empty:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_freq["cas"], y=df_freq["value1"],
        name="Hz", line=dict(color="#00c8ff", width=1.2),
        hovertemplate="%{x|%H:%M}<br><b>%{y:.3f} Hz</b>",
    ))
    fig.add_hline(y=50.0, line_dash="dash", line_color="rgba(128,128,128,0.4)")
    fig.update_layout(**base_layout("Frekvence [Hz]", "#00c8ff"))
    fig.update_yaxes(tickformat=".3f")
    st.plotly_chart(fig, use_container_width=True)

if not df_svr.empty:
    barvy = {"value1":"#bf2837","value2":"#b1b2b7","value3":"#fdc82f","value4":"#13b8f0","value7":"#4baf4f"}
    fig2 = go.Figure()
    for vid, vname in svr_nazvy.items():
        if vid in df_svr.columns:
            fig2.add_trace(go.Bar(
                x=df_svr["cas"], y=df_svr[vid],
                name=vname, marker_color=barvy.get(vid, "#888"),
                hovertemplate=f"%{{x|%H:%M}}<br><b>%{{y:+.2f}} MW</b>",
            ))
    fig2.update_layout(**base_layout("Aktivace SVR v ČR [MW]", "#ffd740"))
    fig2.update_layout(barmode="relative")
    st.plotly_chart(fig2, use_container_width=True)

if not df_cena.empty:
    barvy_c = {"value1":"#00e676","value2":"#ffd740","value3":"#13b8f0","value4":"#4baf4f"}
    fig3 = go.Figure()
    for vid, vname in cena_nazvy.items():
        if vid in df_cena.columns:
            fig3.add_trace(go.Scatter(
                x=df_cena["cas"], y=df_cena[vid],
                name=vname, line=dict(color=barvy_c.get(vid, "#888"), width=1.2),
                hovertemplate=f"%{{x|%H:%M}}<br><b>%{{y:.2f}} EUR/MWh</b>",
            ))
    fig3.update_layout(**base_layout("Aktuální cena RE [EUR/MWh]", "#00e676"))
    st.plotly_chart(fig3, use_container_width=True)

st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400&display=swap" rel="stylesheet">',
    unsafe_allow_html=True
)
st.markdown(
    '<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:4px;">'
    f'<span style="font-size:0.75rem;color:{SUBTEXT};">Data: ČEPS, a.s. – Oficiální SOAP API (cepsdata.asmx)</span>'
    '<span style="font-family:\'Cinzel\',serif;font-size:0.85rem;color:#8899bb;letter-spacing:2px;">Carpe diem, hora ruit</span>'
    '</div>',
    unsafe_allow_html=True
)

if st.session_state.auto_refresh:
    time.sleep(1)
    st.session_state.countdown -= 1
    if st.session_state.countdown <= 0:
        st.cache_data.clear()
        st.session_state.last_update = datetime.now(TZ)
        st.session_state.countdown   = st.session_state.refresh_interval
    st.rerun()
