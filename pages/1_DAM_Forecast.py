"""
pages/1_DAM_Forecast.py – stránka s DAM forecast výsledky
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os

# Přidáme root složku do path aby šel importovat database.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from database import (
        load_latest_forecast,
        load_prices,
        load_bess_summary_history,
        load_forecast_eval,
        load_forecast_history,
    )
    DB_OK = True
except Exception as e:
    DB_OK = False
    DB_ERROR = str(e)

# ── STYL ───────────────────────────────────────────
st.set_page_config(
    page_title="DAM Forecast",
    page_icon="📈",
    layout="wide"
)

st.markdown("""
<style>
  #MainMenu {visibility: hidden;}
  footer {visibility: hidden;}
  header {visibility: hidden;}
  .block-container { padding-top: 1.5rem; }

  .page-title {
    font-family: 'Courier New', monospace;
    font-size: 1.8rem;
    font-weight: 700;
    color: #00e676;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
  }
  .divider { border-top: 1px solid #1e2d50; margin: 0.8rem 0; }

  .col-header {
    font-family: 'Courier New', monospace;
    font-size: 0.7rem;
    letter-spacing: 3px;
    text-transform: uppercase;
    border-bottom: 2px solid;
    padding-bottom: 6px;
    margin-bottom: 12px;
  }
  .col-header.green  { border-color: #00e676; color: #00e676; }
  .col-header.blue   { border-color: #00c8ff; color: #00c8ff; }
  .col-header.yellow { border-color: #ffd740; color: #ffd740; }

  .val-big {
    font-family: 'Courier New', monospace;
    font-size: 1.8rem;
    font-weight: 700;
    line-height: 1.1;
  }
  .row-item {
    display: flex; justify-content: space-between; align-items: center;
    padding: 5px 0; border-bottom: 1px solid #1e2d50;
    font-family: 'Courier New', monospace;
  }
  .row-item:last-child { border-bottom: none; }
  .row-name  { font-size: 0.7rem; color: #8899bb; letter-spacing: 1px; }
  .row-value { font-size: 0.95rem; font-weight: 700; }
  .section-label {
    font-size: 0.62rem; color: #8899bb; text-transform: uppercase;
    letter-spacing: 1px; margin-top: 12px; margin-bottom: 4px;
    font-family: 'Courier New', monospace;
  }
</style>
""", unsafe_allow_html=True)

PLOT_BG  = "#0f1628"
PAPER_BG = "#0a0e1a"
GRID_COL = "#1e2d50"
FONT_COL = "#cdd8f0"

def base_layout(title, color="#00e676"):
    return dict(
        title=dict(text=title, font=dict(color=color, size=13, family="Courier New")),
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=FONT_COL, family="Courier New", size=10),
        hovermode="x unified",
        legend=dict(bgcolor=PLOT_BG, bordercolor=GRID_COL, font=dict(size=10)),
        xaxis=dict(gridcolor=GRID_COL, showgrid=True),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True),
        margin=dict(l=50, r=10, t=40, b=30),
        height=280,
    )

# ── HLAVIČKA ───────────────────────────────────────
st.markdown('<div class="page-title">📈 DAM Forecast</div>', unsafe_allow_html=True)
st.caption("Day-Ahead Market – forecast cen elektřiny CZ | BESS dispatch optimalizace")
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

if not DB_OK:
    st.error(f"❌ Nepodařilo se připojit k databázi: {DB_ERROR}")
    st.stop()

# ── NAČTENÍ DAT ────────────────────────────────────
try:
    df_forecast  = load_latest_forecast()
    df_summary   = load_bess_summary_history(days=30)
    df_eval      = load_forecast_eval(days=30)
    df_prices    = load_prices(days=7)
except Exception as e:
    st.error(f"❌ Chyba při načítání dat: {e}")
    st.stop()

if df_forecast.empty:
    st.warning("⚠ Zatím nejsou k dispozici žádná data. Pipeline ještě nebyla spuštěna.")
    st.stop()

# ── DATUM FORECASTU ────────────────────────────────
forecast_date = pd.to_datetime(df_forecast["forecast_date"].iloc[0]).strftime("%d.%m.%Y")
st.markdown(f'<div style="font-family:\'Courier New\',monospace;font-size:0.8rem;color:#8899bb;">Forecast pro: <span style="color:#00e676">{forecast_date}</span></div>', unsafe_allow_html=True)

# ── TŘI SLOUPCE – SUMMARY ──────────────────────────
col1, _g1, col2, _g2, col3 = st.columns([3, 0.2, 3, 0.2, 3])

with col1:
    st.markdown('<div class="col-header green">💰 Ceny – forecast zítřek</div>', unsafe_allow_html=True)
    if not df_forecast.empty:
        min_row = df_forecast.loc[df_forecast["forecast_price"].idxmin()]
        max_row = df_forecast.loc[df_forecast["forecast_price"].idxmax()]
        avg_price = df_forecast["forecast_price"].mean()
        spread = df_forecast["forecast_price"].max() - df_forecast["forecast_price"].min()

        html = (
            f'<div class="row-item"><span class="row-name">Průměr (baseload)</span>'
            f'<span class="row-value" style="color:#00e676">{avg_price:.2f} EUR/MWh</span></div>'
            f'<div class="row-item"><span class="row-name">Min – hodina {int(min_row["hour"]):02d}:00</span>'
            f'<span class="row-value" style="color:#13b8f0">{min_row["forecast_price"]:.2f} EUR/MWh</span></div>'
            f'<div class="row-item"><span class="row-name">Max – hodina {int(max_row["hour"]):02d}:00</span>'
            f'<span class="row-value" style="color:#ff3d57">{max_row["forecast_price"]:.2f} EUR/MWh</span></div>'
            f'<div class="row-item"><span class="row-name">Spread</span>'
            f'<span class="row-value" style="color:#ffd740">{spread:.2f} EUR/MWh</span></div>'
        )
        st.markdown(html, unsafe_allow_html=True)

with col2:
    st.markdown('<div class="col-header yellow">🔋 BESS Dispatch (1 MW / 2 MWh)</div>', unsafe_allow_html=True)
    if not df_summary.empty:
        latest = df_summary.iloc[0]
        html2 = (
            f'<div class="row-item"><span class="row-name">Profit 1 cyklus</span>'
            f'<span class="row-value" style="color:#00e676">{latest["profit_1cycle_eur"]:.2f} EUR</span></div>'
            f'<div class="row-item"><span class="row-name">Profit 2 cykly</span>'
            f'<span class="row-value" style="color:#00e676">{latest["profit_2cycles_eur"]:.2f} EUR</span></div>'
            f'<div class="row-item"><span class="row-name">Profit 3 cykly</span>'
            f'<span class="row-value" style="color:#00e676">{latest["profit_3cycles_eur"]:.2f} EUR</span></div>'
            f'<div class="row-item"><span class="row-name">Nabíjet v</span>'
            f'<span class="row-value" style="color:#13b8f0">{int(latest["min_hour"]):02d}:00 ({latest["min_price"]:.2f} EUR)</span></div>'
            f'<div class="row-item"><span class="row-name">Vybíjet v</span>'
            f'<span class="row-value" style="color:#ff3d57">{int(latest["max_hour"]):02d}:00 ({latest["max_price"]:.2f} EUR)</span></div>'
        )
        st.markdown(html2, unsafe_allow_html=True)
    else:
        st.warning("Zatím žádná BESS data")

with col3:
    st.markdown('<div class="col-header blue">📊 Přesnost modelu</div>', unsafe_allow_html=True)
    if not df_summary.empty:
        latest = df_summary.iloc[0]
        mae     = latest.get("mae_all")
        rmse    = latest.get("rmse_all")
        median  = latest.get("median_abs_error")
        smape   = latest.get("smape_all_pct")
        days    = latest.get("eval_days_total", 0)

        html3 = (
            f'<div class="row-item"><span class="row-name">MAE</span>'
            f'<span class="row-value" style="color:#cdd8f0">{mae:.2f} EUR/MWh</span></div>'
            f'<div class="row-item"><span class="row-name">RMSE</span>'
            f'<span class="row-value" style="color:#cdd8f0">{rmse:.2f} EUR/MWh</span></div>'
            f'<div class="row-item"><span class="row-name">Median AE</span>'
            f'<span class="row-value" style="color:#cdd8f0">{median:.2f} EUR/MWh</span></div>'
            f'<div class="row-item"><span class="row-name">SMAPE</span>'
            f'<span class="row-value" style="color:#ffd740">{smape:.1f} %</span></div>'
            f'<div class="row-item"><span class="row-name">Hodnoceno dní</span>'
            f'<span class="row-value" style="color:#8899bb">{int(days)}</span></div>'
        ) if all(v is not None for v in [mae, rmse, median, smape]) else '<div style="color:#8899bb;font-size:.8rem;">Zatím nedostatek dat pro hodnocení</div>'
        st.markdown(html3, unsafe_allow_html=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── GRAF: FORECAST ZÍTŘEK ──────────────────────────
if not df_forecast.empty:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_forecast["hour"],
        y=df_forecast["forecast_price"],
        name="Forecast",
        marker_color="#00e676",
        hovertemplate="Hodina %{x}:00<br><b>%{y:.2f} EUR/MWh</b>",
    ))

    # Pokud máme skutečné ceny pro stejný den
    if not df_prices.empty:
        fc_date = pd.to_datetime(df_forecast["forecast_date"].iloc[0]).date()
        actual = df_prices[pd.to_datetime(df_prices["price_date"]).dt.date == fc_date]
        if not actual.empty:
            fig.add_trace(go.Scatter(
                x=actual["hour"], y=actual["price_eur"],
                name="Skutečná cena",
                line=dict(color="#ff3d57", width=2),
                hovertemplate="Hodina %{x}:00<br><b>%{y:.2f} EUR/MWh</b>",
            ))

    fig.update_layout(**base_layout("Forecast cen – zítřek [EUR/MWh]", "#00e676"))
    fig.update_xaxes(tickmode="linear", tick0=0, dtick=1,
                     ticktext=[f"{h:02d}:00" for h in range(24)],
                     tickvals=list(range(24)))
    st.plotly_chart(fig, use_container_width=True)

# ── GRAF: BESS PROFIT HISTORIE ─────────────────────
if not df_summary.empty and len(df_summary) > 1:
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=pd.to_datetime(df_summary["forecast_date"]),
        y=df_summary["profit_1cycle_eur"],
        name="1 cyklus",
        line=dict(color="#00e676", width=1.5),
        hovertemplate="%{x|%d.%m.%Y}<br><b>%{y:.2f} EUR</b>",
    ))
    fig2.add_trace(go.Scatter(
        x=pd.to_datetime(df_summary["forecast_date"]),
        y=df_summary["profit_2cycles_eur"],
        name="2 cykly",
        line=dict(color="#ffd740", width=1.5),
        hovertemplate="%{x|%d.%m.%Y}<br><b>%{y:.2f} EUR</b>",
    ))
    fig2.add_trace(go.Scatter(
        x=pd.to_datetime(df_summary["forecast_date"]),
        y=df_summary["profit_3cycles_eur"],
        name="3 cykly",
        line=dict(color="#00c8ff", width=1.5),
        hovertemplate="%{x|%d.%m.%Y}<br><b>%{y:.2f} EUR</b>",
    ))
    fig2.update_layout(**base_layout("BESS Profit – historie [EUR/den]", "#ffd740"))
    st.plotly_chart(fig2, use_container_width=True)

# ── TABULKA: HODINOVÝ FORECAST ─────────────────────
with st.expander("📋 Hodinový forecast – detail"):
    df_show = df_forecast.copy()
    df_show["hodina"] = df_show["hour"].apply(lambda h: f"{int(h):02d}:00")
    df_show = df_show.rename(columns={
        "forecast_price": "Forecast [EUR/MWh]",
        "model_used":     "Model",
    })[["hodina", "Forecast [EUR/MWh]", "Model"]]
    st.dataframe(df_show, use_container_width=True, hide_index=True)

# ── TABULKA: EVAL HISTORIE ─────────────────────────
with st.expander("📋 Hodnocení přesnosti – posledních 30 dní"):
    if not df_eval.empty:
        st.dataframe(df_eval, use_container_width=True, hide_index=True)
    else:
        st.info("Zatím žádná hodnocení.")

st.caption("Data: ENTSO-E Transparency Platform | Model: HistGradientBoostingRegressor")
