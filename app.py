import streamlit as st
import requests
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ──────────────────────────────────────────────
# KONFIGURACE
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="ČEPS Data",
    page_icon="⚡",
    layout="wide"
)

SOAP_URL = "https://www.ceps.cz/CepsData/CepsDataService.svc"

HEADERS = {
    "Content-Type": "application/soap+xml; charset=utf-8",
}

# ──────────────────────────────────────────────
# SOAP ŠABLONA
# ──────────────────────────────────────────────

SOAP_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<soap12:Envelope
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:xsd="http://www.w3.org/2001/XMLSchema"
    xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">
  <soap12:Body>
    <{action} xmlns="http://www.ceps.cz/CepsData/">
      <dateFrom>{date_from}</dateFrom>
      <dateTo>{date_to}</dateTo>
      <agregation>{agregation}</agregation>
      <function>AVG</function>
      <version>RT</version>
      <para1>{para1}</para1>
    </{action}>
  </soap12:Body>
</soap12:Envelope>"""

# ──────────────────────────────────────────────
# FUNKCE: VOLÁNÍ API
# ──────────────────────────────────────────────

def volej_ceps(action, date_from, date_to, agregation="QH", para1=""):
    """Zavolá ČEPS SOAP API a vrátí parsovaný XML strom."""
    body = SOAP_TEMPLATE.format(
        action=action,
        date_from=date_from,
        date_to=date_to,
        agregation=agregation,
        para1=para1,
    )
    try:
        resp = requests.post(
            SOAP_URL,
            data=body.encode("utf-8"),
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        return ET.fromstring(resp.content)
    except requests.exceptions.Timeout:
        st.error("⏱️ Server ČEPS neodpovídá (timeout 30 s). Zkuste to znovu.")
        return None
    except requests.exceptions.HTTPError as e:
        st.error(f"❌ HTTP chyba: {e}")
        return None
    except ET.ParseError as e:
        st.error(f"❌ Chyba při parsování XML: {e}")
        return None

# ──────────────────────────────────────────────
# FUNKCE: PARSOVÁNÍ XML → DataFrame
# ──────────────────────────────────────────────

def xml_na_df(root, sloupce):
    """
    Prochází XML a vytváří DataFrame.
    sloupce = seznam názvů sloupců (odpovídají tagům v XML).
    """
    ns = {"c": "http://www.ceps.cz/CepsData/"}
    radky = []

    # XML může mít různé struktury – hledáme 'DataPoint' nebo 'Item'
    for tag in ["DataPoint", "Item", "Row", "data"]:
        items = root.findall(f".//{tag}", ns)
        if not items:
            # zkusit bez namespace
            items = root.findall(f".//{tag}")
        if items:
            break

    for item in items:
        radek = {}
        for sloupec in sloupce:
            # zkusit s namespace i bez
            el = item.find(f"c:{sloupec}", ns) or item.find(sloupec)
            radek[sloupec] = el.text if el is not None else None
        radky.append(radek)

    if not radky:
        return pd.DataFrame()

    df = pd.DataFrame(radky)

    # Převod časového sloupce
    for col in ["date", "Date", "dateTime", "DateTime", "ts"]:
        if col in df.columns:
            df["cas"] = pd.to_datetime(df[col], errors="coerce")
            df = df.drop(columns=[col])
            break

    # Převod číselných sloupců
    for col in df.columns:
        if col != "cas":
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df

# ──────────────────────────────────────────────
# UI: POSTRANNÍ PANEL
# ──────────────────────────────────────────────

with st.sidebar:
    st.title("⚡ ČEPS Data")
    st.markdown("Data české přenosové soustavy")
    st.divider()

    # Výběr období
    obdobi = st.selectbox(
        "Zobrazit období",
        ["Dnešní den", "Posledních 24 hodin", "Posledních 7 dní"],
        index=0,
    )

    # Výběr agregace
    agregace_map = {
        "Minutová": "MI",
        "Čtvrthodinová": "QH",
        "Hodinová": "H",
    }
    agregace_label = st.selectbox(
        "Agregace dat",
        list(agregace_map.keys()),
        index=1,
    )
    agregace = agregace_map[agregace_label]

    st.divider()

    # Výběr dat
    st.markdown("**Co zobrazit:**")
    zobraz_vyrobu = st.checkbox("Výroba dle zdrojů", value=True)
    zobraz_zatizeni = st.checkbox("Zatížení / spotřeba", value=True)
    zobraz_toky = st.checkbox("Přeshraniční toky", value=False)

    st.divider()
    nacist = st.button("🔄 Načíst data", use_container_width=True)

# ──────────────────────────────────────────────
# VÝPOČET DATOVÉHO ROZSAHU
# ──────────────────────────────────────────────

now = datetime.utcnow()

if obdobi == "Dnešní den":
    date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
    date_to = now
elif obdobi == "Posledních 24 hodin":
    date_from = now - timedelta(hours=24)
    date_to = now
else:  # 7 dní
    date_from = now - timedelta(days=7)
    date_to = now

fmt = "%Y-%m-%dT%H:%M:%S"
str_from = date_from.strftime(fmt)
str_to = date_to.strftime(fmt)

# ──────────────────────────────────────────────
# HLAVNÍ OBSAH
# ──────────────────────────────────────────────

st.title("⚡ ČEPS – přenosová soustava ČR")
st.caption(f"Rozsah: {str_from} → {str_to} UTC | Agregace: {agregace_label}")

if not nacist:
    st.info("👈 Vyberte parametry v levém panelu a klikněte na **Načíst data**.")
    st.stop()

# ──────────────────────────────────────────────
# VÝROBA
# ──────────────────────────────────────────────

if zobraz_vyrobu:
    st.subheader("🏭 Výroba dle zdrojů (MW)")

    with st.spinner("Načítám data výroby..."):
        root = volej_ceps("Generation", str_from, str_to, agregace)

    if root is not None:
        # Sloupce odpovídají XML tagům v odpovědi ČEPS
        sloupce_vyroby = [
            "date", "TPP", "CCGT", "NPP", "HPP", "PsPP",
            "AltPP", "ApPP", "PVPP", "WPP"
        ]
        df_vyroba = xml_na_df(root, sloupce_vyroby)

        if df_vyroba.empty:
            st.warning("Data výroby nebyla nalezena v odpovědi serveru.")
            with st.expander("🔍 Zobrazit raw XML (pro diagnostiku)"):
                st.code(ET.tostring(root, encoding="unicode")[:3000])
        else:
            # Přejmenování pro lepší čitelnost
            nazvy = {
                "TPP": "Uhlí",
                "CCGT": "Plyn/CCGT",
                "NPP": "Jádro",
                "HPP": "Vodní",
                "PsPP": "Přečerpávání",
                "AltPP": "Biomasa",
                "ApPP": "Průmyslové",
                "PVPP": "Solární",
                "WPP": "Větrné",
            }
            df_vyroba = df_vyroba.rename(columns=nazvy)

            # Graf
            zdroje = [v for v in nazvy.values() if v in df_vyroba.columns]
            df_plot = df_vyroba[["cas"] + zdroje].dropna(subset=["cas"])

            fig = px.area(
                df_plot.melt(id_vars="cas", value_vars=zdroje,
                             var_name="Zdroj", value_name="MW"),
                x="cas", y="MW", color="Zdroj",
                title="Výroba elektřiny dle zdrojů",
                labels={"cas": "Čas (UTC)"},
            )
            fig.update_layout(hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("📋 Zobrazit tabulku"):
                st.dataframe(df_vyroba, use_container_width=True)

# ──────────────────────────────────────────────
# ZATÍŽENÍ / SPOTŘEBA
# ──────────────────────────────────────────────

if zobraz_zatizeni:
    st.subheader("📈 Zatížení soustavy (MW)")

    with st.spinner("Načítám data zatížení..."):
        root = volej_ceps("Load", str_from, str_to, agregace)

    if root is not None:
        sloupce_load = ["date", "load", "Load", "value", "Value"]
        df_load = xml_na_df(root, sloupce_load)

        if df_load.empty:
            st.warning("Data zatížení nebyla nalezena.")
            with st.expander("🔍 Zobrazit raw XML"):
                st.code(ET.tostring(root, encoding="unicode")[:3000])
        else:
            # Najdi správný sloupec s hodnotou
            hodnotovy_sloupec = next(
                (c for c in df_load.columns if c != "cas"), None
            )
            if hodnotovy_sloupec:
                fig2 = px.line(
                    df_load.dropna(subset=["cas"]),
                    x="cas", y=hodnotovy_sloupec,
                    title="Zatížení přenosové soustavy",
                    labels={"cas": "Čas (UTC)", hodnotovy_sloupec: "MW"},
                )
                fig2.update_traces(line_color="#e74c3c", line_width=2)
                st.plotly_chart(fig2, use_container_width=True)

                with st.expander("📋 Zobrazit tabulku"):
                    st.dataframe(df_load, use_container_width=True)

# ──────────────────────────────────────────────
# PŘESHRANIČNÍ TOKY
# ──────────────────────────────────────────────

if zobraz_toky:
    st.subheader("🔀 Přeshraniční toky (MW)")

    sousede = {
        "Německo (TenneT)": "TenneT",
        "Německo (50Hz)": "50HzT",
        "Slovensko": "SEPS",
        "Polsko": "PSE",
        "Rakousko": "APG",
    }

    vybrany_soused_label = st.selectbox(
        "Vyberte sousední soustavu", list(sousede.keys())
    )
    vybrany_soused = sousede[vybrany_soused_label]

    with st.spinner(f"Načítám toky přes {vybrany_soused_label}..."):
        root = volej_ceps(
            "CrossborderFlows", str_from, str_to, agregace, para1=vybrany_soused
        )

    if root is not None:
        sloupce_toky = ["date", "flow", "Flow", "value", "Value"]
        df_toky = xml_na_df(root, sloupce_toky)

        if df_toky.empty:
            st.warning("Data přeshraničních toků nebyla nalezena.")
            with st.expander("🔍 Zobrazit raw XML"):
                st.code(ET.tostring(root, encoding="unicode")[:3000])
        else:
            hodnotovy_sloupec = next(
                (c for c in df_toky.columns if c != "cas"), None
            )
            if hodnotovy_sloupec:
                fig3 = px.bar(
                    df_toky.dropna(subset=["cas"]),
                    x="cas", y=hodnotovy_sloupec,
                    title=f"Přeshraniční tok: ČR ↔ {vybrany_soused_label}",
                    labels={"cas": "Čas (UTC)", hodnotovy_sloupec: "MW"},
                    color=hodnotovy_sloupec,
                    color_continuous_scale=["#e74c3c", "#95a5a6", "#2ecc71"],
                    color_continuous_midpoint=0,
                )
                st.plotly_chart(fig3, use_container_width=True)
                st.caption("Kladné hodnoty = export z ČR, záporné = import do ČR")

                with st.expander("📋 Zobrazit tabulku"):
                    st.dataframe(df_toky, use_container_width=True)

# ──────────────────────────────────────────────
# PATIČKA
# ──────────────────────────────────────────────

st.divider()
st.caption("Data: ČEPS, a.s. – SOAP API (https://www.ceps.cz/en/web-services)")
