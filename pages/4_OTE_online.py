"""
pages/4_OTE_online.py – OTE online: DAM ceny a odchylky elektřiny
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import xml.etree.ElementTree as ET
import pytz
import sys
import os
from datetime import datetime, timedelta, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from navigation import show_nav

st.set_page_config(page_title="OTE online", page_icon="🔌", layout="wide")

# ── TÉMA ───────────────────────────────────────────
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
    LEG_COL  = "#1a2035"
    BTN_TEMA = "🌙"

st.markdown(f"""
<style>
  #MainMenu {{visibility:hidden;}} footer {{visibility:hidden;}} header {{visibility:hidden;}}
  .block-container {{ padding-top:1.2rem; background:{BG}; }}
  .stApp {{ background:{BG}; }}
  .page-title {{
    font-family:'Courier New',monospace; font-size:1.8rem; font-weight:700;
    color:#00c8ff; letter-spacing:3px; text-transform:uppercase; margin-bottom:0.3rem;
  }}
  .divider {{ border-top:1px solid {BORDER}; margin:0.8rem 0; }}
  .col-header {{
    font-family:'Courier New',monospace; font-size:0.7rem; letter-spacing:3px;
    text-transform:uppercase; border-bottom:2px solid; padding-bottom:6px; margin-bottom:12px;
  }}
  .col-header.dam   {{ border-color:#00e676; color:#00e676; }}
  .col-header.odch  {{ border-color:#ffd740; color:#ffd740; }}
  .row-item {{
    display:flex; justify-content:space-between; align-items:center;
    padding:5px 0; border-bottom:1px solid {BORDER}; font-family:'Courier New',monospace;
  }}
  .row-item:last-child {{ border-bottom:none; }}
  .row-name  {{ font-size:0.7rem; color:{SUBTEXT}; letter-spacing:1px; }}
  .row-value {{ font-size:0.95rem; font-weight:700; }}
  .val-big {{ font-family:'Courier New',monospace; font-size:2rem; font-weight:700; line-height:1.1; color:#00e676; margin-bottom:4px; }}
  .section-label {{
    font-size:0.62rem; color:{SUBTEXT}; text-transform:uppercase;
    letter-spacing:1px; margin-top:12px; margin-bottom:4px; font-family:'Courier New',monospace;
  }}
  div[data-testid="stButton"] button {{
    background:transparent !important; border:1px solid {BORDER} !important;
    color:{SUBTEXT} !important; font-size:0.8rem !important;
    padding:4px 10px !important; font-family:'Courier New',monospace !important;
  }}
  div[data-testid="stButton"] button:hover {{ border-color:#00c8ff !important; color:#00c8ff !important; }}
  div[data-testid="stSelectbox"] > div {{
    background:{BG} !important; border-color:{BORDER} !important; color:{TEXT} !important;
    font-family:'Courier New',monospace !important; font-size:0.8rem !important;
  }}
</style>
""", unsafe_allow_html=True)

TZ   = pytz.timezone("Europe/Prague")
WSDL = "https://www.ote-cr.cz/pw-data/services/PublicDataService"
NS   = "http://www.ote-cr.cz/schema/service/public"

# ── OTE SOAP HELPER ────────────────────────────────
def soap_call(action: str, body_inner: str) -> ET.Element:
    envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:pub="{NS}">
  <soapenv:Header/>
  <soapenv:Body>
    {body_inner}
  </soapenv:Body>
</soapenv:Envelope>"""
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{NS}/{action}"',
    }
    resp = requests.post(WSDL, data=envelope.encode("utf-8"), headers=headers, timeout=30)
    resp.raise_for_status()
    return ET.fromstring(resp.content)


def get_dam_index(start_date: str, end_date: str) -> pd.DataFrame:
    """GetDamIndexE — base/peak/offpeak load indexy."""
    body = f"""<pub:GetDamIndexE>
      <pub:StartDate>{start_date}</pub:StartDate>
      <pub:EndDate>{end_date}</pub:EndDate>
    </pub:GetDamIndexE>"""
    root = soap_call("GetDamIndexE", body)
    rows = []
    for item in root.iter(f"{{{NS}}}Item"):
        rows.append({
            "date":         item.findtext(f"{{{NS}}}Date"),
            "base_load":    _float(item.findtext(f"{{{NS}}}BaseLoad")),
            "peak_load":    _float(item.findtext(f"{{{NS}}}PeakLoad")),
            "offpeak_load": _float(item.findtext(f"{{{NS}}}OffpeakLoad")),
            "eur_rate":     _float(item.findtext(f"{{{NS}}}EurRate")),
            "base_volume":  _float(item.findtext(f"{{{NS}}}BaseLoadVolume")),
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date")


def get_dam_price_period(delivery_date: str) -> pd.DataFrame:
    """GetDamPricePeriodE — hodinové ceny pro jeden den."""
    body = f"""<pub:GetDamPricePeriodE>
      <pub:DeliveryDate>{delivery_date}</pub:DeliveryDate>
    </pub:GetDamPricePeriodE>"""
    root = soap_call("GetDamPricePeriodE", body)
    rows = []
    for item in root.iter(f"{{{NS}}}Item"):
        rows.append({
            "period": _int(item.findtext(f"{{{NS}}}Period")),
            "price":  _float(item.findtext(f"{{{NS}}}Price")),
            "volume": _float(item.findtext(f"{{{NS}}}Volume")),
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.sort_values("period")


def get_imbalance(start_date: str, end_date: str) -> pd.DataFrame:
    """GetImbalanceSettlementPeriodE — odchylky elektřina."""
    body = f"""<pub:GetImbalanceSettlementPeriodE>
      <pub:StartDate>{start_date}</pub:StartDate>
      <pub:EndDate>{end_date}</pub:EndDate>
    </pub:GetImbalanceSettlementPeriodE>"""
    root = soap_call("GetImbalanceSettlementPeriodE", body)
    rows = []
    for item in root.iter(f"{{{NS}}}Item"):
        rows.append({
            "date":             item.findtext(f"{{{NS}}}Date"),
            "period":           _int(item.findtext(f"{{{NS}}}Period")),
            "price_plus":       _float(item.findtext(f"{{{NS}}}PricePlus")),
            "price_minus":      _float(item.findtext(f"{{{NS}}}PriceMinus")),
            "imbalance_volume": _float(item.findtext(f"{{{NS}}}ImbalanceVolume")),
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df["datetime"] = df["date"] + pd.to_timedelta((df["period"] - 1) * 15, unit="m")
    return df.sort_values("datetime")


def _float(val):
    try: return float(val)
    except: return None

def _int(val):
    try: return int(val)
    except: return None


# ── STAŽENÍ DAT ────────────────────────────────────
@st.cache_data(ttl=300)
def load_all_data(period_days: int):
    today     = date.today()
    yesterday = today - timedelta(days=1)
    start     = today - timedelta(days=period_days)

    df_index   = get_dam_index(start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    df_hourly  = get_dam_price_period(today.strftime("%Y-%m-%d"))
    if df_hourly.empty:
        df_hourly = get_dam_price_period(yesterday.strftime("%Y-%m-%d"))
    df_odch    = get_imbalance(start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    return df_index, df_hourly, df_odch


def base_layout(title, color="#00c8ff"):
    return dict(
        title=dict(text=title, font=dict(color=color, size=13, family="Courier New")),
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=LEG_COL, family="Courier New", size=11),
        hovermode="x unified",
        legend=dict(bgcolor=PLOT_BG, bordercolor=BORDER, font=dict(size=11, color=LEG_COL)),
        xaxis=dict(gridcolor=GRID_COL, showgrid=True, color=LEG_COL),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True, color=LEG_COL),
        margin=dict(l=50, r=10, t=40, b=30), height=240,
    )


# ── HLAVIČKA ───────────────────────────────────────
header_l, header_r = st.columns([7, 3])
with header_l:
    st.markdown('<div class="page-title">🔌 OTE online</div>', unsafe_allow_html=True)
with header_r:
    nav_sp, nav_sel, nav_tema = st.columns([1, 3, 1])
    with nav_sel:
        show_nav("nav_ote")
    with nav_tema:
        if st.button(BTN_TEMA, use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

# ── OVLÁDÁNÍ ───────────────────────────────────────
ctrl_l, ctrl_r = st.columns([2, 8])
with ctrl_l:
    if st.button("🔄 Obnovit", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

OBDOBI = {"1 týden": 7, "1 měsíc": 30, "6 měsíců": 180, "12 měsíců": 365}
with ctrl_r:
    sel_col, _ = st.columns([2, 6])
    with sel_col:
        obdobi_label = st.selectbox("Období grafů", list(OBDOBI.keys()), index=1, label_visibility="collapsed")
period_days = OBDOBI[obdobi_label]

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── DATA ───────────────────────────────────────────
with st.spinner("Načítám data z OTE..."):
    try:
        df_index, df_hourly, df_odch = load_all_data(period_days)
        last_str = datetime.now(TZ).strftime("%d.%m.%Y %H:%M:%S")
        st.markdown(
            f'<div style="font-size:0.75rem;color:{SUBTEXT};font-family:monospace;margin-bottom:0.5rem;">'
            f'Aktualizace: <span style="color:#00e676">{last_str}</span> &nbsp;|&nbsp; '
            f'Zdroj: OTE, a.s. – veřejné SOAP API</div>',
            unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"❌ Chyba při načítání dat z OTE: {e}")
        st.stop()

# ── SLOUPCE: DAM + ODCHYLKY ────────────────────────
col_dam, _g, col_odch = st.columns([3, 0.2, 3])

with col_dam:
    st.markdown('<div class="col-header dam">⚡ DAM – Denní trh elektřiny</div>', unsafe_allow_html=True)

    # Dnešní indexy
    if not df_index.empty:
        last_idx = df_index.iloc[-1]
        base   = last_idx["base_load"]
        peak   = last_idx["peak_load"]
        offpk  = last_idx["offpeak_load"]
        date_s = pd.Timestamp(last_idx["date"]).strftime("%d.%m.%Y")

        st.markdown(f'<div class="section-label">Base load ({date_s})</div>', unsafe_allow_html=True)
        color_b = "#00e676" if base is not None else SUBTEXT
        val_b   = f"{base:.2f} EUR/MWh" if base is not None else "—"
        st.markdown(f'<div class="val-big" style="color:{color_b}">{val_b}</div>', unsafe_allow_html=True)

        html_idx = ""
        for label, val, color in [
            ("Peak load",    peak,  "#ffd740"),
            ("Offpeak load", offpk, "#13b8f0"),
        ]:
            v = f"{val:.2f} EUR/MWh" if val is not None else "—"
            html_idx += f'<div class="row-item"><span class="row-name">{label}</span><span class="row-value" style="color:{color}">{v}</span></div>'
        st.markdown(html_idx, unsafe_allow_html=True)

    # Dnešní hodinové ceny
    if not df_hourly.empty:
        st.markdown('<div class="section-label" style="margin-top:14px">Hodinové ceny (15min periody)</div>', unsafe_allow_html=True)
        fig_h = go.Figure()
        fig_h.add_trace(go.Scatter(
            x=df_hourly["period"], y=df_hourly["price"],
            name="EUR/MWh", line=dict(color="#00e676", width=1.5),
            hovertemplate="Perioda %{x}<br><b>%{y:.2f} EUR/MWh</b>",
        ))
        layout_h = base_layout("Dnešní ceny DAM [EUR/MWh]", "#00e676")
        layout_h["height"] = 180
        layout_h["xaxis"]["title"] = "Perioda (1=00:00)"
        fig_h.update_layout(**layout_h)
        st.plotly_chart(fig_h, use_container_width=True)

with col_odch:
    st.markdown('<div class="col-header odch">📊 Odchylky elektřiny</div>', unsafe_allow_html=True)

    if not df_odch.empty:
        last_odch = df_odch.iloc[-1]
        p_plus  = last_odch["price_plus"]
        p_minus = last_odch["price_minus"]
        imb_vol = last_odch["imbalance_volume"]
        last_dt = pd.Timestamp(last_odch["datetime"]).strftime("%d.%m. %H:%M")

        st.markdown(f'<div class="section-label">Poslední perioda ({last_dt})</div>', unsafe_allow_html=True)
        color_p = "#ff3d57" if p_plus is not None and p_plus > 200 else "#00e676"
        val_p   = f"{p_plus:.2f} EUR/MWh" if p_plus is not None else "—"
        st.markdown(f'<div class="val-big" style="color:{color_p}">{val_p}</div>', unsafe_allow_html=True)

        html_odch = ""
        for label, val, color in [
            ("Cena odchylky −",   p_minus, "#13b8f0"),
            ("Imbalance volume",  imb_vol, "#ffd740"),
        ]:
            v = f"{val:.2f}" if val is not None else "—"
            unit = " EUR/MWh" if "Cena" in label else " MWh"
            html_odch += f'<div class="row-item"><span class="row-name">{label}</span><span class="row-value" style="color:{color}">{v}{unit}</span></div>'
        st.markdown(html_odch, unsafe_allow_html=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── GRAFY: BASE LOAD HISTORIE ──────────────────────
if not df_index.empty:
    fig_base = go.Figure()
    fig_base.add_trace(go.Scatter(
        x=df_index["date"], y=df_index["base_load"],
        name="Base load", line=dict(color="#00e676", width=1.5),
        hovertemplate="%{x|%d.%m.%Y}<br><b>%{y:.2f} EUR/MWh</b>",
        fill="tozeroy", fillcolor="rgba(0,230,118,0.07)",
    ))
    fig_base.add_trace(go.Scatter(
        x=df_index["date"], y=df_index["peak_load"],
        name="Peak load", line=dict(color="#ffd740", width=1.2),
        hovertemplate="%{x|%d.%m.%Y}<br><b>%{y:.2f} EUR/MWh</b>",
    ))
    fig_base.add_trace(go.Scatter(
        x=df_index["date"], y=df_index["offpeak_load"],
        name="Offpeak load", line=dict(color="#13b8f0", width=1.2),
        hovertemplate="%{x|%d.%m.%Y}<br><b>%{y:.2f} EUR/MWh</b>",
    ))
    layout_base = base_layout(f"DAM indexy – {obdobi_label} [EUR/MWh]", "#00e676")
    layout_base["height"] = 260
    fig_base.update_layout(**layout_base)
    st.plotly_chart(fig_base, use_container_width=True)

# ── GRAFY: ODCHYLKY HISTORIE ──────────────────────
if not df_odch.empty:
    fig_odch = go.Figure()
    fig_odch.add_trace(go.Scatter(
        x=df_odch["datetime"], y=df_odch["price_plus"],
        name="Cena odchylky +", line=dict(color="#ff3d57", width=1.0),
        hovertemplate="%{x|%d.%m %H:%M}<br><b>%{y:.2f} EUR/MWh</b>",
    ))
    fig_odch.add_trace(go.Scatter(
        x=df_odch["datetime"], y=df_odch["price_minus"],
        name="Cena odchylky −", line=dict(color="#13b8f0", width=1.0),
        hovertemplate="%{x|%d.%m %H:%M}<br><b>%{y:.2f} EUR/MWh</b>",
    ))
    layout_odch = base_layout(f"Odchylky elektřiny – {obdobi_label} [EUR/MWh]", "#ffd740")
    layout_odch["height"] = 260
    fig_odch.update_layout(**layout_odch)
    st.plotly_chart(fig_odch, use_container_width=True)

# ── FOOTER ─────────────────────────────────────────
st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400&display=swap" rel="stylesheet">',
    unsafe_allow_html=True
)
st.markdown(
    '<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:4px;">'
    f'<span style="font-size:0.75rem;color:{SUBTEXT};">Data: OTE, a.s. – veřejné SOAP API</span>'
    '<span style="font-size:0.75rem;color:#8899bb;font-style:italic;">oldrich by claude</span>'
    '<span style="font-family:\'Cinzel\',serif;font-size:0.85rem;color:#8899bb;letter-spacing:2px;">Ora et labora</span>'
    '</div>',
    unsafe_allow_html=True
)
