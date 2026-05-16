"""
pages/2_mFRR_Orderbook.py – mFRR+ a mFRR- orderbook nejnovějšího dne
"""

import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from navigation import show_nav

try:
    from database import load_mfrr_orderbook, load_mfrr_minus_orderbook
    DB_OK = True
except Exception as e:
    DB_OK = False
    DB_ERROR = str(e)

st.set_page_config(page_title="mFRR Orderbooks", page_icon="📋", layout="wide")

# ── TÉMA ───────────────────────────────────────────
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

if st.session_state.dark_mode:
    BG      = "#0a0e1a"
    BORDER  = "#1e2d50"
    TEXT    = "#cdd8f0"
    SUBTEXT = "#8899bb"
    PLUS_BG = "#0a1a10"
    MINUS_BG= "#1a0a0e"
    PLUS_BORDER  = "#1e5030"
    MINUS_BORDER = "#501e2d"
    BTN_TEMA = "☀️"
else:
    BG      = "#f5f7fa"
    BORDER  = "#dde3ef"
    TEXT    = "#1a2035"
    SUBTEXT = "#6677aa"
    PLUS_BG = "#f0fff4"
    MINUS_BG= "#fff0f3"
    PLUS_BORDER  = "#b2dfdb"
    MINUS_BORDER = "#ffb3c1"
    BTN_TEMA = "🌙"

st.markdown(f"""
<style>
  #MainMenu {{visibility:hidden;}} footer {{visibility:hidden;}} header {{visibility:hidden;}}
  .block-container {{ padding-top:1.2rem; background:{BG}; }}
  .stApp {{ background:{BG}; }}

  .page-title {{
    font-family:'Courier New',monospace; font-size:1.8rem; font-weight:700;
    color:#ffd740; letter-spacing:3px; text-transform:uppercase; margin-bottom:0.3rem;
  }}
  .divider {{ border-top:1px solid {BORDER}; margin:0.8rem 0; }}

  .tbl-header-plus {{
    font-family:'Courier New',monospace; font-size:0.75rem; letter-spacing:3px;
    text-transform:uppercase; color:#00e676; border-bottom:2px solid #00e676;
    padding-bottom:6px; margin-bottom:10px;
  }}
  .tbl-header-minus {{
    font-family:'Courier New',monospace; font-size:0.75rem; letter-spacing:3px;
    text-transform:uppercase; color:#ff3d57; border-bottom:2px solid #ff3d57;
    padding-bottom:6px; margin-bottom:10px;
  }}
  .tbl-info {{
    font-family:'Courier New',monospace; font-size:0.75rem; color:{SUBTEXT}; margin-bottom:8px;
  }}

  div[data-testid="stButton"] button {{
    background:transparent !important; border:1px solid {BORDER} !important;
    color:{SUBTEXT} !important; font-size:0.8rem !important;
    padding:4px 10px !important; font-family:'Courier New',monospace !important;
  }}
  div[data-testid="stButton"] button:hover {{
    border-color:#ffd740 !important; color:#ffd740 !important;
  }}
</style>
""", unsafe_allow_html=True)

# ── HLAVIČKA ───────────────────────────────────────
header_l, header_r = st.columns([7, 3])
with header_l:
    st.markdown('<div class="page-title">📋 mFRR Orderbooks</div>', unsafe_allow_html=True)
with header_r:
    nav_sp, nav_sel, nav_tema = st.columns([1, 3, 1])
    with nav_sel:
        show_nav("nav_mfrr")
    with nav_tema:
        if st.button(BTN_TEMA, use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

if not DB_OK:
    st.error(f"❌ Nepodařilo se připojit k databázi: {DB_ERROR}")
    st.stop()

# ── DATA ───────────────────────────────────────────
try:
    df_plus  = load_mfrr_orderbook()
    df_minus = load_mfrr_minus_orderbook()
except Exception as e:
    st.error(f"❌ Chyba při načítání dat: {e}")
    st.stop()

# ── DATUM ──────────────────────────────────────────
date_plus  = pd.to_datetime(df_plus["trade_date"].iloc[0]).strftime("%d.%m.%Y")  if not df_plus.empty  else "—"
date_minus = pd.to_datetime(df_minus["trade_date"].iloc[0]).strftime("%d.%m.%Y") if not df_minus.empty else "—"

st.markdown(
    f'<div style="font-family:\'Courier New\',monospace;font-size:0.8rem;color:{SUBTEXT};margin-bottom:16px;">'
    f'mFRR+ datum: <span style="color:#00e676">{date_plus}</span>'
    f' &nbsp;|&nbsp; mFRR- datum: <span style="color:#ff3d57">{date_minus}</span>'
    f'</div>',
    unsafe_allow_html=True
)

# ── DVA SLOUPCE S TABULKAMI ────────────────────────
col_plus, _gap, col_minus = st.columns([5, 0.3, 5])

COL_CONFIG_PLUS = {
    "Product Type":       st.column_config.TextColumn(width="small"),
    "Position":           st.column_config.NumberColumn(width="small", format="%d"),
    "Quantity [MW]":      st.column_config.NumberColumn(width="small", format="%.2f"),
    "Price [EUR/MW]":     st.column_config.NumberColumn(width="small", format="%.2f"),
    "Cum. Qty [MW]":      st.column_config.NumberColumn(width="small", format="%.2f"),
}

with col_plus:
    st.markdown('<div class="tbl-header-plus">▲ mFRR+ (nabídky regulace nahoru)</div>', unsafe_allow_html=True)
    if not df_plus.empty:
        st.markdown(
            f'<div class="tbl-info">Nabídek: <b>{len(df_plus)}</b> &nbsp;|&nbsp; '
            f'Max objem: <b>{df_plus["cum_quantity_mw"].max():.1f} MW</b> &nbsp;|&nbsp; '
            f'Cena max: <b>{df_plus["price_eur_mw"].max():.2f} EUR/MW</b></div>',
            unsafe_allow_html=True
        )
        df_show_plus = df_plus[["product_type","position","quantity_mw","price_eur_mw","cum_quantity_mw"]].copy()
        df_show_plus.columns = ["Product Type","Position","Quantity [MW]","Price [EUR/MW]","Cum. Qty [MW]"]
        df_show_plus = df_show_plus.round(2)
        st.dataframe(df_show_plus, use_container_width=True, hide_index=True, column_config=COL_CONFIG_PLUS)
    else:
        st.warning("Žádná mFRR+ data")

with col_minus:
    st.markdown('<div class="tbl-header-minus">▼ mFRR- (nabídky regulace dolů)</div>', unsafe_allow_html=True)
    if not df_minus.empty:
        st.markdown(
            f'<div class="tbl-info">Nabídek: <b>{len(df_minus)}</b> &nbsp;|&nbsp; '
            f'Max objem: <b>{df_minus["cum_quantity_mw"].max():.1f} MW</b> &nbsp;|&nbsp; '
            f'Cena max: <b>{df_minus["price_eur_mw"].max():.2f} EUR/MW</b></div>',
            unsafe_allow_html=True
        )
        df_show_minus = df_minus[["product_type","position","quantity_mw","price_eur_mw","cum_quantity_mw"]].copy()
        df_show_minus.columns = ["Product Type","Position","Quantity [MW]","Price [EUR/MW]","Cum. Qty [MW]"]
        df_show_minus = df_show_minus.round(2)

        COL_CONFIG_MINUS = {
            "Product Type":   st.column_config.TextColumn(width="small"),
            "Position":       st.column_config.NumberColumn(width="small", format="%d"),
            "Quantity [MW]":  st.column_config.NumberColumn(width="small", format="%.2f"),
            "Price [EUR/MW]": st.column_config.NumberColumn(width="small", format="%.2f"),
            "Cum. Qty [MW]":  st.column_config.NumberColumn(width="small", format="%.2f"),
        }
        st.dataframe(df_show_minus, use_container_width=True, hide_index=True, column_config=COL_CONFIG_MINUS)
    else:
        st.warning("Žádná mFRR- data")

st.caption("Data: ENTSO-E Transparency Platform – mFRR Balancing Capacity")
