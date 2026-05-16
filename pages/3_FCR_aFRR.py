"""
pages/3_FCR_aFRR.py – FCR a aFRR výsledky tendrů
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from navigation import show_nav

try:
    from database import load_fcr_overview, load_afrr_overview, load_afrr_orderbook
    DB_OK = True
except Exception as e:
    DB_OK = False
    DB_ERROR = str(e)

st.set_page_config(page_title="FCR & aFRR", page_icon="🏷️", layout="wide")

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
  .section-title {{
    font-family:'Courier New',monospace; font-size:0.75rem; letter-spacing:3px;
    text-transform:uppercase; padding-bottom:6px; margin-bottom:10px; border-bottom:2px solid;
  }}
  .section-title.fcr   {{ color:#ffd740; border-color:#ffd740; }}
  .section-title.afrr  {{ color:#00e676; border-color:#00e676; }}
  .section-title.ob    {{ color:#00c8ff; border-color:#00c8ff; }}
  .row-item {{
    display:flex; justify-content:space-between; align-items:center;
    padding:4px 0; border-bottom:1px solid {BORDER}; font-family:'Courier New',monospace;
  }}
  .row-item:last-child {{ border-bottom:none; }}
  .row-name  {{ font-size:0.7rem; color:{SUBTEXT}; }}
  .row-value {{ font-size:0.85rem; font-weight:700; }}
  div[data-testid="stButton"] button {{
    background:transparent !important; border:1px solid {BORDER} !important;
    color:{SUBTEXT} !important; font-size:0.8rem !important;
    padding:4px 10px !important; font-family:'Courier New',monospace !important;
  }}
  div[data-testid="stButton"] button:hover {{ border-color:#00c8ff !important; color:#00c8ff !important; }}
</style>
""", unsafe_allow_html=True)

# ── HLAVIČKA ───────────────────────────────────────
header_l, header_r = st.columns([7, 3])
with header_l:
    st.markdown('<div class="page-title">🏷️ FCR & aFRR</div>', unsafe_allow_html=True)
with header_r:
    nav_sp, nav_sel, nav_tema = st.columns([1, 3, 1])
    with nav_sel:
        show_nav("nav_fcr_afrr")
    with nav_tema:
        if st.button(BTN_TEMA, use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

if not DB_OK:
    st.error(f"❌ Nepodařilo se připojit k databázi: {DB_ERROR}")
    st.stop()

try:
    df_fcr  = load_fcr_overview()
    df_afrr = load_afrr_overview()
except Exception as e:
    st.error(f"❌ Chyba při načítání dat: {e}")
    st.stop()

if df_fcr.empty and df_afrr.empty:
    st.warning("⚠ Zatím nejsou k dispozici žádná data.")
    st.stop()

# Datum
trade_date = pd.to_datetime(df_fcr["trade_date"].iloc[0]).strftime("%d.%m.%Y") if not df_fcr.empty else "—"
st.markdown(
    f'<div style="font-family:\'Courier New\',monospace;font-size:0.8rem;color:{SUBTEXT};margin-bottom:12px;">'
    f'Datum dodávky: <span style="color:#00c8ff">{trade_date}</span>'
    f' &nbsp;|&nbsp; Zdroj: <span style="color:{SUBTEXT}">regelleistung.net</span>'
    f'</div>',
    unsafe_allow_html=True
)

# ── FCR PŘEHLED ────────────────────────────────────
st.markdown('<div class="section-title fcr">⚡ FCR – Frequency Containment Reserve</div>', unsafe_allow_html=True)

if not df_fcr.empty:
    # Přejmenování bloků
    def fmt_block(name):
        return name.replace("NEGPOS_", "").replace("_", "–")

    df_fcr_show = df_fcr.copy()
    df_fcr_show["Blok"] = df_fcr_show["product_name"].apply(fmt_block)
    df_fcr_show = df_fcr_show.rename(columns={
        "crossborder_price":  "Crossborder [EUR/MW]",
        "cz_demand_mw":       "CZ Poptávka [MW]",
        "cz_price":           "CZ Cena [EUR/MW]",
        "cz_deficit_surplus": "CZ Deficit(-)/Přebytek(+) [MW]",
    })[["Blok", "Crossborder [EUR/MW]", "CZ Poptávka [MW]", "CZ Cena [EUR/MW]", "CZ Deficit(-)/Přebytek(+) [MW]"]]

    st.dataframe(
        df_fcr_show.round(2),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Blok":                           st.column_config.TextColumn(width="small"),
            "Crossborder [EUR/MW]":           st.column_config.NumberColumn(width="medium", format="%.2f"),
            "CZ Poptávka [MW]":               st.column_config.NumberColumn(width="small",  format="%.0f"),
            "CZ Cena [EUR/MW]":               st.column_config.NumberColumn(width="medium", format="%.2f"),
            "CZ Deficit(-)/Přebytek(+) [MW]": st.column_config.NumberColumn(width="medium", format="%.0f"),
        }
    )

    # Mini graf FCR cen
    fig_fcr = go.Figure()
    fig_fcr.add_trace(go.Bar(
        x=df_fcr_show["Blok"],
        y=df_fcr_show["CZ Cena [EUR/MW]"],
        name="CZ cena",
        marker_color="#ffd740",
        hovertemplate="%{x}<br><b>%{y:.2f} EUR/MW</b>",
    ))
    fig_fcr.add_trace(go.Scatter(
        x=df_fcr_show["Blok"],
        y=df_fcr_show["Crossborder [EUR/MW]"],
        name="Crossborder cena",
        line=dict(color="#00c8ff", width=2, dash="dot"),
        hovertemplate="%{x}<br><b>%{y:.2f} EUR/MW</b>",
    ))
    fig_fcr.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=LEG_COL, family="Courier New", size=11),
        height=220, margin=dict(l=50, r=10, t=30, b=30),
        hovermode="x unified",
        legend=dict(bgcolor=PLOT_BG, bordercolor=BORDER, font=dict(size=11, color=LEG_COL)),
        xaxis=dict(gridcolor=GRID_COL, color=LEG_COL),
        yaxis=dict(gridcolor=GRID_COL, color=LEG_COL, title="EUR/MW"),
    )
    st.plotly_chart(fig_fcr, use_container_width=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── aFRR PŘEHLED ───────────────────────────────────
st.markdown('<div class="section-title afrr">📡 aFRR – Automatic Frequency Restoration Reserve</div>', unsafe_allow_html=True)

if not df_afrr.empty:
    def fmt_afrr_product(p):
        p = p.replace("POS_", "▲ ").replace("NEG_", "▼ ").replace("_", "–")
        return p

    df_afrr_show = df_afrr.copy()
    df_afrr_show["Produkt"] = df_afrr_show["product"].apply(fmt_afrr_product)
    df_afrr_show = df_afrr_show.rename(columns={
        "total_marginal_price": "Total Marginální [EUR/MW/h]",
        "cz_min_price":         "CZ Min [EUR/MW/h]",
        "cz_avg_price":         "CZ Průměr [EUR/MW/h]",
        "cz_marginal_price":    "CZ Marginální [EUR/MW/h]",
        "cz_import_export":     "CZ Import(-)/Export(+) [MW]",
        "cz_allocated_mw":      "CZ Alokováno [MW]",
    })[["Produkt", "Total Marginální [EUR/MW/h]", "CZ Min [EUR/MW/h]",
        "CZ Průměr [EUR/MW/h]", "CZ Marginální [EUR/MW/h]",
        "CZ Import(-)/Export(+) [MW]", "CZ Alokováno [MW]"]]

    st.dataframe(
        df_afrr_show.round(2),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Produkt":                      st.column_config.TextColumn(width="small"),
            "Total Marginální [EUR/MW/h]":  st.column_config.NumberColumn(width="medium", format="%.2f"),
            "CZ Min [EUR/MW/h]":            st.column_config.NumberColumn(width="small",  format="%.2f"),
            "CZ Průměr [EUR/MW/h]":         st.column_config.NumberColumn(width="small",  format="%.2f"),
            "CZ Marginální [EUR/MW/h]":     st.column_config.NumberColumn(width="medium", format="%.2f"),
            "CZ Import(-)/Export(+) [MW]":  st.column_config.NumberColumn(width="medium", format="%.0f"),
            "CZ Alokováno [MW]":            st.column_config.NumberColumn(width="small",  format="%.0f"),
        }
    )

    # Graf aFRR marginálních cen
    df_pos = df_afrr[df_afrr["product"].str.startswith("POS")].copy()
    df_neg = df_afrr[df_afrr["product"].str.startswith("NEG")].copy()
    blok_labels = ["00–04", "04–08", "08–12", "12–16", "16–20", "20–24"]

    fig_afrr = go.Figure()
    if not df_pos.empty:
        fig_afrr.add_trace(go.Bar(
            x=blok_labels[:len(df_pos)],
            y=df_pos["cz_marginal_price"].values,
            name="▲ POS marginální CZ",
            marker_color="rgba(0,230,118,0.7)",
            hovertemplate="%{x}<br><b>%{y:.2f} EUR/MW/h</b>",
        ))
    if not df_neg.empty:
        fig_afrr.add_trace(go.Bar(
            x=blok_labels[:len(df_neg)],
            y=df_neg["cz_marginal_price"].values,
            name="▼ NEG marginální CZ",
            marker_color="rgba(255,61,87,0.7)",
            hovertemplate="%{x}<br><b>%{y:.2f} EUR/MW/h</b>",
        ))
    fig_afrr.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=LEG_COL, family="Courier New", size=11),
        height=220, margin=dict(l=50, r=10, t=30, b=30),
        barmode="group", hovermode="x unified",
        legend=dict(bgcolor=PLOT_BG, bordercolor=BORDER, font=dict(size=11, color=LEG_COL)),
        xaxis=dict(gridcolor=GRID_COL, color=LEG_COL),
        yaxis=dict(gridcolor=GRID_COL, color=LEG_COL, title="EUR/MW/h"),
    )
    st.plotly_chart(fig_afrr, use_container_width=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── aFRR ORDERBOOK ─────────────────────────────────
st.markdown('<div class="section-title ob">📊 aFRR Orderbook – CZ nabídky</div>', unsafe_allow_html=True)

# Výběr bloku
bloky_pos = ["POS_00_04","POS_04_08","POS_08_12","POS_12_16","POS_16_20","POS_20_24"]
bloky_neg = ["NEG_00_04","NEG_04_08","NEG_08_12","NEG_12_16","NEG_16_20","NEG_20_24"]
blok_labels_map = {
    "POS_00_04":"00–04", "POS_04_08":"04–08", "POS_08_12":"08–12",
    "POS_12_16":"12–16", "POS_16_20":"16–20", "POS_20_24":"20–24",
    "NEG_00_04":"00–04", "NEG_04_08":"04–08", "NEG_08_12":"08–12",
    "NEG_12_16":"12–16", "NEG_16_20":"16–20", "NEG_20_24":"20–24",
}

sel_col, _ = st.columns([3, 7])
with sel_col:
    selected_block = st.selectbox(
        "Časový blok:",
        options=["00–04","04–08","08–12","12–16","16–20","20–24"],
        key="afrr_block"
    )

# Mapování výběru na product kódy
block_map = {
    "00–04": ("POS_00_04","NEG_00_04"),
    "04–08": ("POS_04_08","NEG_04_08"),
    "08–12": ("POS_08_12","NEG_08_12"),
    "12–16": ("POS_12_16","NEG_12_16"),
    "16–20": ("POS_16_20","NEG_16_20"),
    "20–24": ("POS_20_24","NEG_20_24"),
}
prod_pos, prod_neg = block_map[selected_block]

try:
    df_ob_pos = load_afrr_orderbook(prod_pos)
    df_ob_neg = load_afrr_orderbook(prod_neg)
except Exception as e:
    st.error(f"❌ Chyba: {e}")
    st.stop()

# Dvě tabulky vedle sebe
col_pos, _gap, col_neg = st.columns([5, 0.3, 5])

COL_CFG = {
    "Cena [EUR/MW/h]":    st.column_config.NumberColumn(width="medium", format="%.2f"),
    "Nabídka [MW]":       st.column_config.NumberColumn(width="small",  format="%.2f"),
    "Alokováno [MW]":     st.column_config.NumberColumn(width="small",  format="%.2f"),
}

with col_pos:
    st.markdown(
        f'<div style="font-family:\'Courier New\',monospace;font-size:0.7rem;letter-spacing:2px;'
        f'color:#00e676;border-bottom:2px solid #00e676;padding-bottom:4px;margin-bottom:8px;">▲ aFRR+ | {selected_block}</div>',
        unsafe_allow_html=True
    )
    if not df_ob_pos.empty:
        st.markdown(
            f'<div style="font-family:\'Courier New\',monospace;font-size:0.72rem;color:{SUBTEXT};margin-bottom:6px;">'
            f'Nabídek: <b>{len(df_ob_pos)}</b> &nbsp;|&nbsp; Celkem: <b>{df_ob_pos["offered_mw"].sum():.1f} MW</b></div>',
            unsafe_allow_html=True
        )
        df_s = df_ob_pos[["capacity_price","offered_mw","allocated_mw"]].copy()
        df_s.columns = ["Cena [EUR/MW/h]","Nabídka [MW]","Alokováno [MW]"]
        st.dataframe(df_s.round(2), use_container_width=True, hide_index=True, column_config=COL_CFG)
    else:
        st.info("Žádné nabídky")

with col_neg:
    st.markdown(
        f'<div style="font-family:\'Courier New\',monospace;font-size:0.7rem;letter-spacing:2px;'
        f'color:#ff3d57;border-bottom:2px solid #ff3d57;padding-bottom:4px;margin-bottom:8px;">▼ aFRR- | {selected_block}</div>',
        unsafe_allow_html=True
    )
    if not df_ob_neg.empty:
        st.markdown(
            f'<div style="font-family:\'Courier New\',monospace;font-size:0.72rem;color:{SUBTEXT};margin-bottom:6px;">'
            f'Nabídek: <b>{len(df_ob_neg)}</b> &nbsp;|&nbsp; Celkem: <b>{df_ob_neg["offered_mw"].sum():.1f} MW</b></div>',
            unsafe_allow_html=True
        )
        df_s = df_ob_neg[["capacity_price","offered_mw","allocated_mw"]].copy()
        df_s.columns = ["Cena [EUR/MW/h]","Nabídka [MW]","Alokováno [MW]"]
        st.dataframe(df_s.round(2), use_container_width=True, hide_index=True, column_config=COL_CFG)
    else:
        st.info("Žádné nabídky")

# Graf hloubky trhu pro vybraný blok
if not df_ob_pos.empty or not df_ob_neg.empty:
    st.markdown('<div style="margin-top:16px"></div>', unsafe_allow_html=True)
    fig_ob = go.Figure()

    if not df_ob_pos.empty:
        fig_ob.add_trace(go.Bar(
            x=-df_ob_pos["offered_mw"],
            y=df_ob_pos["capacity_price"].round(2),
            orientation="h",
            name="aFRR+",
            marker_color="rgba(0,230,118,0.7)",
            marker_line=dict(color="#00e676", width=0.5),
            customdata=df_ob_pos["offered_mw"],
            hovertemplate="aFRR+<br>Cena: <b>%{y:.2f} EUR/MW/h</b><br>Množství: <b>%{customdata:.2f} MW</b>",
        ))

    if not df_ob_neg.empty:
        fig_ob.add_trace(go.Bar(
            x=df_ob_neg["offered_mw"],
            y=df_ob_neg["capacity_price"].round(2),
            orientation="h",
            name="aFRR-",
            marker_color="rgba(255,61,87,0.7)",
            marker_line=dict(color="#ff3d57", width=0.5),
            customdata=df_ob_neg["offered_mw"],
            hovertemplate="aFRR-<br>Cena: <b>%{y:.2f} EUR/MW/h</b><br>Množství: <b>%{customdata:.2f} MW</b>",
        ))

    max_x = max(
        df_ob_pos["offered_mw"].max() if not df_ob_pos.empty else 0,
        df_ob_neg["offered_mw"].max() if not df_ob_neg.empty else 0,
    )

    fig_ob.add_vline(x=0, line_color="rgba(255,255,255,0.3)", line_width=1)
    fig_ob.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=LEG_COL, family="Courier New", size=11),
        height=400, margin=dict(l=80, r=20, t=40, b=50),
        showlegend=False, hovermode="closest", barmode="overlay",
        xaxis=dict(
            title="Objem [MW]", gridcolor=GRID_COL, color=LEG_COL,
            tickvals=[-30,-20,-10,0,10,20,30],
            ticktext=["30","20","10","0","10","20","30"],
        ),
        yaxis=dict(title="Cena [EUR/MW/h]", gridcolor=GRID_COL, color=LEG_COL),
        annotations=[
            dict(x=-max_x, y=1.04, xref="x", yref="paper",
                 text="◄ aFRR+", showarrow=False,
                 font=dict(color="#00e676", size=12, family="Courier New"), xanchor="left"),
            dict(x=max_x, y=1.04, xref="x", yref="paper",
                 text="aFRR- ►", showarrow=False,
                 font=dict(color="#ff3d57", size=12, family="Courier New"), xanchor="right"),
        ]
    )
    st.plotly_chart(fig_ob, use_container_width=True)

st.caption("Data: regelleistung.net – FCR & aFRR Capacity Market Results")
