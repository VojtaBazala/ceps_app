# navigation.py – centrální navigace
# Přidání nové stránky = jeden řádek zde

import streamlit as st

PAGES = [
    ("⚡ ČEPS online",      "CEPS_online.py"),
    ("📈 DAM Forecast",     "pages/1_DAM_Forecast.py"),
    ("📋 mFRR Orderbooks",  "pages/2_mFRR_Orderbook.py"),
    ("🏷️ FCR & aFRR",       "pages/3_FCR_aFRR.py"),
]

def show_nav(current_key: str):
    options = ["— Přejít na —"] + [p[0] for p in PAGES]
    nav = st.selectbox("", options, key=current_key, label_visibility="collapsed")
    if nav != "— Přejít na —":
        for name, path in PAGES:
            if nav == name:
                st.switch_page(path)
                break
