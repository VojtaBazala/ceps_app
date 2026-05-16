"""
pages/2_mFRR_Orderbook.py – mFRR+ orderbook nejnovějšího dne
"""

import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from navigation import show_nav

try:
    from database import load_mfrr_orderbook
    DB_OK = True
except Exception as e:
    DB_OK = False; DB_ERROR = str(e)

st.set_page_config(page_title="mFRR+ Orderbook", page_icon="📋", layout="wide")

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = True

if st.session_state.dark_mode:
    BG="#0a0e1a"; BORDER="#1e2d50"; TEXT="#cdd8f0"; SUBTEXT="#8899bb"; BTN_TEMA="☀️"
else:
    BG="#f5f7fa"; BORDER="#dde3ef"; TEXT="#1a2035"; SUBTEXT="#6677aa"; BTN_TEMA="🌙"

st.markdown(f"""
<style>
  #MainMenu {{visibility:hidden;}} footer {{visibility:hidden;}} header {{visibility:hidden;}}
  .block-container {{ padding-top:1.2rem; background:{BG}; }} .stApp {{ background:{BG}; }}
  .page-title {{ font-family:'Courier New',monospace; font-size:1.8rem; font-weight:700; color:#ffd740; letter-spacing:3px; text-transform:uppercase; margin-bottom:0.3rem; }}
  .divider {{ border-top:1px solid {BORDER}; margin:0.8rem 0; }}
  div[data-testid="stButton"] button {{ background:transparent !important; border:1px solid {BORDER} !important; color:{SUBTEXT} !important; font-size:0.8rem !important; padding:4px 10px !important; font-family:'Courier New',monospace !important; }}
  div[data-testid="stButton"] button:hover {{ border-color:#ffd740 !important; color:#ffd740 !important; }}
</style>
""", unsafe_allow_html=True)

# ── HLAVIČKA ───────────────────────────────────────
header_l, header_r = st.columns([7, 3])
with header_l:
    st.markdown('<div class="page-title">📋 mFRR+ Orderbook</div>', unsafe_allow_html=True)
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
    st.error(f"❌ Nepodařilo se připojit k databázi: {DB_ERROR}"); st.stop()

try:
    df = load_mfrr_orderbook()
except Exception as e:
    st.error(f"❌ Chyba při načítání dat: {e}"); st.stop()

if df.empty:
    st.warning("⚠ Zatím nejsou k dispozici žádná data."); st.stop()

trade_date = pd.to_datetime(df["trade_date"].iloc[0]).strftime("%d.%m.%Y")
st.markdown(
    f'<div style="font-family:\'Courier New\',monospace;font-size:0.8rem;color:{SUBTEXT};">'
    f'Datum: <span style="color:#ffd740">{trade_date}</span>'
    f' &nbsp;|&nbsp; Počet nabídek: <span style="color:#ffd740">{len(df)}</span></div>',
    unsafe_allow_html=True
)
st.markdown('<div style="margin-bottom:12px"></div>', unsafe_allow_html=True)

df_show = df[["product_type", "position", "quantity_mw", "price_eur_mw", "cum_quantity_mw"]].copy()
df_show.columns = ["Product Type", "Position", "Quantity [MW]", "Price [EUR/MW]", "Cum. Quantity [MW]"]
df_show = df_show.round(2)

st.dataframe(
    df_show,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Product Type":       st.column_config.TextColumn(width="medium"),
        "Position":           st.column_config.NumberColumn(width="small", format="%d"),
        "Quantity [MW]":      st.column_config.NumberColumn(width="small", format="%.2f"),
        "Price [EUR/MW]":     st.column_config.NumberColumn(width="medium", format="%.2f"),
        "Cum. Quantity [MW]": st.column_config.NumberColumn(width="medium", format="%.2f"),
    }
)

st.caption("Data: ENTSO-E Transparency Platform – mFRR+ Balancing Capacity")
