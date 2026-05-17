"""
pages/4_OTE_online.py – OTE online: DAM ceny (ENTSO-E) + odchylky (ČEPS)
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
import xml.etree.ElementTree as ET
import pytz
import sys
import os
from datetime import datetime, timedelta, date, timezone
from zeep import Client
from zeep.transports import Transport

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
  .col-header.dam  {{ border-color:#00e676; color:#00e676; }}
  .col-header.odch {{ border-color:#ffd740; color:#ffd740; }}
  .row-item {{
    display:flex; justify-content:space-between; align-items:center;
    padding:5px 0; border-bottom:1px solid {BORDER}; font-family:'Courier New',monospace;
  }}
  .row-item:last-child {{ border-bottom:none; }}
  .row-name  {{ font-size:0.7rem; color:{SUBTEXT}; letter-spacing:1px; }}
  .row-value {{ font-size:0.95rem; font-weight:700; }}
  .val-big {{
    font-family:'Courier New',monospace; font-size:2rem; font-weight:700;
    line-height:1.1; color:#00e676; margin-bottom:4px;
  }}
  .section-label {{
    font-size:0.62rem; color:{SUBTEXT}; text-transform:uppercase;
    letter-spacing:1px; margin-top:12px; margin-bottom:4px; font-family:'Courier New',monospace;
  }}
  div[data-testid="stButton"] button {{
    background:transparent !important; border:1px solid {BORDER} !important;
    color:{SUBTEXT} !important; font-size:0.8rem !important;
    padding:4px 10px !important; font-family:'Courier New',monospace !important;
  }}
  div[data-testid="stButton"] button:hover {{
    border-color:#00c8ff !important; color:#00c8ff !important;
  }}
</style>
""", unsafe_allow_html=True)

TZ         = pytz.timezone("Europe/Prague")
CEPS_WSDL  = "https://vip-prod-service-00-azapp.azurewebsites.net/_layouts/cepsdata.asmx?WSDL"
ENTSOE_URL = "https://web-api.tp.entsoe.eu/api"
CZ_ZONE    = "10YCZ-CEPS-----N"


# ── ENTSO-E: DAM ceny ─────────────────────────────
def entsoe_time(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M")


def get_dam_prices(start_utc: datetime, end_utc: datetime, token: str) -> pd.DataFrame:
    params = {
        "securityToken": token,
        "documentType":  "A44",
        "in_Domain":     CZ_ZONE,
        "out_Domain":    CZ_ZONE,
        "periodStart":   entsoe_time(start_utc),
        "periodEnd":     entsoe_time(end_utc),
    }
    resp = requests.get(ENTSOE_URL, params=params, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    if "Acknowledgement_MarketDocument" in root.tag:
        return pd.DataFrame()

    ns_uri = root.tag.split("}")[0].strip("{")
    ns = {"n": ns_uri}
    rows = []
    for ts in root.findall("n:TimeSeries", ns):
        for period in ts.findall("n:Period", ns):
            ti = period.find("n:timeInterval", ns)
            if ti is None:
                continue
            start = ti.findtext("n:start", namespaces=ns)
            resolution = period.findtext("n:resolution", namespaces=ns)
            if not start:
                continue
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            step = timedelta(hours=1) if resolution == "PT60M" else timedelta(minutes=15)
            for point in period.findall("n:Point", ns):
                pos   = int(point.findtext("n:position", "1", namespaces=ns))
                price = float(point.findtext("n:price.amount", "0", namespaces=ns))
                dt_utc = start_dt + step * (pos - 1)
                rows.append({"datetime_utc": dt_utc, "price_eur_mwh": price})

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.drop_duplicates("datetime_utc").sort_values("datetime_utc").reset_index(drop=True)
    df["datetime_cet"] = pd.to_datetime(df["datetime_utc"]).dt.tz_convert("Europe/Prague")
    df["date"] = df["datetime_cet"].dt.date
    df["hour"] = df["datetime_cet"].dt.hour
    return df


def compute_dam_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    rows = []
    for d, grp in df.groupby("date"):
        base  = grp["price_eur_mwh"].mean()
        peak  = grp[grp["hour"].between(8, 19)]["price_eur_mwh"].mean()
        offpk = grp[~grp["hour"].between(8, 19)]["price_eur_mwh"].mean()
        rows.append({"date": d, "base_load": base, "peak_load": peak, "offpeak_load": offpk})
    return pd.DataFrame(rows)


# ── ČEPS: odhadovaná cena odchylky ────────────────
@st.cache_resource
def get_ceps_client():
    session = requests.Session()
    return Client(CEPS_WSDL, transport=Transport(session=session))


def ceps_xml_na_df(result) -> pd.DataFrame:
    NS_CEPS = "https://www.ceps.cz/CepsData/StructuredData/1.0"
    items = result.findall(f"{{{NS_CEPS}}}data/{{{NS_CEPS}}}item")
    if not items:
        items = result.findall("data/item")
    rows = []
    for item in items:
        radek = {"cas": item.get("date")}
        for k, v in item.attrib.items():
            if k != "date":
                try:    radek[k] = float(v)
                except: radek[k] = None
        rows.append(radek)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["cas"] = pd.to_datetime(df["cas"], utc=True, errors="coerce").dt.tz_convert("Europe/Prague")
    return df


def get_odchylky(date_from, date_to) -> pd.DataFrame:
    client = get_ceps_client()
    result = client.service.OdhadovanaCenaOdchylky(dateFrom=date_from, dateTo=date_to)
    return ceps_xml_na_df(result)


# ── CACHE ──────────────────────────────────────────
@st.cache_data(ttl=300)
def load_dam(period_days: int, token: str) -> pd.DataFrame:
    now_utc   = datetime.now(timezone.utc)
    start_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=period_days)
    end_utc   = now_utc.replace(hour=23, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return get_dam_prices(start_utc, end_utc, token)


@st.cache_data(ttl=55)
def load_odchylky(period_days: int) -> pd.DataFrame:
    now_local = datetime.now(TZ).replace(tzinfo=None)
    pulnoc    = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    date_from = pulnoc - timedelta(days=min(period_days - 1, 29))
    date_to   = now_local
    return get_odchylky(date_from, date_to)


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

# ── TOKEN ──────────────────────────────────────────
token = os.environ.get("ENTSOE_API_TOKEN", "")
if not token:
    st.error("❌ ENTSOE_API_TOKEN není nastaven v Heroku config vars!")
    st.stop()

# ── DATA ───────────────────────────────────────────
with st.spinner("Načítám data..."):
    df_dam   = pd.DataFrame()
    df_index = pd.DataFrame()
    df_odch  = pd.DataFrame()

    try:
        df_dam   = load_dam(period_days, token)
        df_index = compute_dam_index(df_dam)
    except Exception as e:
        st.warning(f"⚠️ DAM data (ENTSO-E): {e}")

    try:
        df_odch = load_odchylky(period_days)
    except Exception as e:
        st.warning(f"⚠️ Odchylky (ČEPS): {e}")

tz_label = "SELČ" if bool(datetime.now(TZ).dst()) else "SEČ"
st.markdown(
    f'<div style="font-size:0.75rem;color:{SUBTEXT};font-family:monospace;margin-bottom:0.5rem;">'
    f'Aktualizace: <span style="color:#00e676">{datetime.now(TZ).strftime("%d.%m.%Y %H:%M:%S")} {tz_label}</span>'
    f' &nbsp;|&nbsp; DAM: ENTSO-E &nbsp;|&nbsp; Odchylky: ČEPS SOAP</div>',
    unsafe_allow_html=True
)

# ── SLOUPCE ────────────────────────────────────────
col_dam, _g, col_odch_col = st.columns([3, 0.2, 3])

# ── DAM ────────────────────────────────────────────
with col_dam:
    st.markdown('<div class="col-header dam">⚡ DAM – Denní trh elektřiny</div>', unsafe_allow_html=True)

    if not df_index.empty:
        last_idx = df_index.iloc[-1]
        base  = last_idx["base_load"]
        peak  = last_idx["peak_load"]
        offpk = last_idx["offpeak_load"]
        date_s = pd.Timestamp(last_idx["date"]).strftime("%d.%m.%Y")

        st.markdown(f'<div class="section-label">Base load ({date_s})</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="val-big">{base:.2f} EUR/MWh</div>', unsafe_allow_html=True)

        html = ""
        for label, val, color in [
            ("Peak load (h8–h19)", peak,  "#ffd740"),
            ("Offpeak load",       offpk, "#13b8f0"),
        ]:
            v = f"{val:.2f} EUR/MWh" if val is not None else "—"
            html += (
                f'<div class="row-item">'
                f'<span class="row-name">{label}</span>'
                f'<span class="row-value" style="color:{color}">{v}</span>'
                f'</div>'
            )
        st.markdown(html, unsafe_allow_html=True)

        if not df_dam.empty:
            latest_date = df_dam["date"].max()
            df_today    = df_dam[df_dam["date"] == latest_date].copy()
            if not df_today.empty:
                st.markdown('<div class="section-label" style="margin-top:14px">Hodinový profil</div>', unsafe_allow_html=True)
                df_h = df_today.groupby("hour", as_index=False)["price_eur_mwh"].mean()
                fig_h = go.Figure()
                fig_h.add_trace(go.Scatter(
                    x=df_h["hour"], y=df_h["price_eur_mwh"],
                    name="EUR/MWh", line=dict(color="#00e676", width=1.5),
                    fill="tozeroy", fillcolor="rgba(0,230,118,0.07)",
                    hovertemplate="h%{x}<br><b>%{y:.2f} EUR/MWh</b>",
                ))
                layout_h = base_layout("Hodinové ceny DAM [EUR/MWh]", "#00e676")
                layout_h["height"] = 180
                layout_h["xaxis"]["tickmode"] = "linear"
                layout_h["xaxis"]["tick0"] = 0
                layout_h["xaxis"]["dtick"] = 2
                fig_h.update_layout(**layout_h)
                st.plotly_chart(fig_h, use_container_width=True)
    else:
        st.warning("DAM data nejsou dostupná")

# ── ODCHYLKY ───────────────────────────────────────
with col_odch_col:
    st.markdown('<div class="col-header odch">📊 Odhadovaná cena odchylky</div>', unsafe_allow_html=True)

    val_cols = [c for c in df_odch.columns if c != "cas"] if not df_odch.empty else []
    df_odch_valid = df_odch[df_odch["cas"].notna()] if not df_odch.empty else pd.DataFrame()
    # Pokud jsou všechny cas NaT, použij celý df
    if df_odch_valid.empty and not df_odch.empty:
        df_odch_valid = df_odch.copy()

    if not df_odch_valid.empty and val_cols:
        last    = df_odch_valid.iloc[-1]
        cas_val = last["cas"]
        if pd.isna(cas_val):
            cas_str = "aktuální"
        else:
            cas_str = pd.Timestamp(cas_val).strftime("%d.%m. %H:%M")
        first_val = last[val_cols[0]] if val_cols else None

        st.markdown(f'<div class="section-label">Aktuální ({cas_str})</div>', unsafe_allow_html=True)
        if first_val is not None:
            color_v = "#ff3d57" if first_val > 3000 else "#ffd740" if first_val > 1500 else "#00e676"
            st.markdown(
                f'<div class="val-big" style="color:{color_v}">{first_val:.2f} Kč/MWh</div>',
                unsafe_allow_html=True
            )

        html = ""
        for col in val_cols[1:]:
            v = last[col]
            if v is not None:
                html += (
                    f'<div class="row-item">'
                    f'<span class="row-name">{col}</span>'
                    f'<span class="row-value" style="color:{TEXT}">{v:.2f}</span>'
                    f'</div>'
                )
        if html:
            st.markdown(html, unsafe_allow_html=True)
    else:
        st.warning("Data odchylek nejsou dostupná")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── GRAF: DAM INDEXY HISTORIE ─────────────────────
if not df_index.empty:
    fig_base = go.Figure()
    fig_base.add_trace(go.Scatter(
        x=df_index["date"], y=df_index["base_load"],
        name="Base load", line=dict(color="#00e676", width=1.5),
        fill="tozeroy", fillcolor="rgba(0,230,118,0.07)",
        hovertemplate="%{x|%d.%m.%Y}<br><b>%{y:.2f} EUR/MWh</b>",
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

# ── GRAF: ODCHYLKY HISTORIE ───────────────────────
if not df_odch_valid.empty and val_cols:
    fig_odch = go.Figure()
    colors = ["#ffd740", "#ff3d57", "#13b8f0", "#00e676"]
    for i, col in enumerate(val_cols[:3]):
        fig_odch.add_trace(go.Scatter(
            x=df_odch_valid["cas"], y=df_odch_valid[col],
            name=col, line=dict(color=colors[i % len(colors)], width=1.0),
            hovertemplate=f"%{{x|%d.%m %H:%M}}<br><b>%{{y:.2f}}</b>",
        ))
    layout_odch = base_layout(f"Odhadovaná cena odchylky – {obdobi_label}", "#ffd740")
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
    f'<span style="font-size:0.75rem;color:{SUBTEXT};">DAM: ENTSO-E &nbsp;|&nbsp; Odchylky: ČEPS, a.s.</span>'
    '<span style="font-size:0.75rem;color:#8899bb;font-style:italic;">oldrich by claude</span>'
    '<span style="font-family:\'Cinzel\',serif;font-size:0.85rem;color:#8899bb;letter-spacing:2px;">Ora et labora</span>'
    '</div>',
    unsafe_allow_html=True
)
