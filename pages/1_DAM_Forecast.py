"""
pages/1_DAM_Forecast.py – stránka s DAM forecast výsledky
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os

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
  .col-header.green { border-color: #00e676; color: #00e676; }
  .col-header.blue  { border-color: #00c8ff; color: #00c8ff; }

  .row-item {
    display: flex; justify-content: space-between; align-items: center;
    padding: 5px 0; border-bottom: 1px solid #1e2d50;
    font-family: 'Courier New', monospace;
  }
  .row-item:last-child { border-bottom: none; }
  .row-name  { font-size: 0.7rem; color: #8899bb; letter-spacing: 1px; }
  .row-value { font-size: 0.95rem; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

PLOT_BG  = "#0f1628"
PAPER_BG = "#0a0e1a"
GRID_COL = "#1e2d50"
FONT_COL = "#cdd8f0"

def base_layout(title, color="#00e676", height=280):
    return dict(
        title=dict(text=title, font=dict(color=color, size=13, family="Courier New")),
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=FONT_COL, family="Courier New", size=10),
        hovermode="x unified",
        legend=dict(bgcolor=PLOT_BG, bordercolor=GRID_COL, font=dict(size=10)),
        xaxis=dict(gridcolor=GRID_COL, showgrid=True),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True),
        margin=dict(l=50, r=10, t=40, b=30),
        height=height,
    )

# ── HLAVIČKA ───────────────────────────────────────
st.markdown('<div class="page-title">📈 DAM Forecast</div>', unsafe_allow_html=True)
st.caption("Predikce hodinových cen na následující den")
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

if not DB_OK:
    st.error(f"❌ Nepodařilo se připojit k databázi: {DB_ERROR}")
    st.stop()

# ── NAČTENÍ DAT ────────────────────────────────────
try:
    df_forecast = load_latest_forecast()
    df_summary  = load_bess_summary_history(days=30)
    df_eval     = load_forecast_eval(days=30)
    df_prices   = load_prices(days=7)
    df_hist     = load_forecast_history(days=7)
except Exception as e:
    st.error(f"❌ Chyba při načítání dat: {e}")
    st.stop()

if df_forecast.empty:
    st.warning("⚠ Zatím nejsou k dispozici žádná data. Pipeline ještě nebyla spuštěna.")
    st.stop()

# ── DATUM FORECASTU ────────────────────────────────
forecast_date_str = pd.to_datetime(df_forecast["forecast_date"].iloc[0]).strftime("%d.%m.%Y")
run_date_str = pd.to_datetime(df_forecast["run_date"].iloc[0]).strftime("%d.%m.%Y") if "run_date" in df_forecast.columns else "—"

st.markdown(
    f'<div style="font-family:\'Courier New\',monospace;font-size:0.8rem;color:#8899bb;">'
    f'Forecast pro: <span style="color:#00e676">{forecast_date_str}</span>'
    f' &nbsp;|&nbsp; Vytvořeno: <span style="color:#8899bb">{run_date_str}</span>'
    f'</div>',
    unsafe_allow_html=True
)

st.markdown('<div style="margin-bottom:12px"></div>', unsafe_allow_html=True)

# ── DVA SLOUPCE ────────────────────────────────────
col1, _g1, col2 = st.columns([3, 0.3, 3])

with col1:
    st.markdown('<div class="col-header green">💰 Ceny – forecast zítřek</div>', unsafe_allow_html=True)
    min_row   = df_forecast.loc[df_forecast["forecast_price"].idxmin()]
    max_row   = df_forecast.loc[df_forecast["forecast_price"].idxmax()]
    avg_price = df_forecast["forecast_price"].mean()
    spread    = df_forecast["forecast_price"].max() - df_forecast["forecast_price"].min()

    st.markdown(
        f'<div class="row-item"><span class="row-name">Průměr (baseload)</span>'
        f'<span class="row-value" style="color:#00e676">{avg_price:.2f} EUR/MWh</span></div>'
        f'<div class="row-item"><span class="row-name">Min – hodina {int(min_row["hour"]):02d}:00</span>'
        f'<span class="row-value" style="color:#13b8f0">{min_row["forecast_price"]:.2f} EUR/MWh</span></div>'
        f'<div class="row-item"><span class="row-name">Max – hodina {int(max_row["hour"]):02d}:00</span>'
        f'<span class="row-value" style="color:#ff3d57">{max_row["forecast_price"]:.2f} EUR/MWh</span></div>'
        f'<div class="row-item"><span class="row-name">Spread</span>'
        f'<span class="row-value" style="color:#ffd740">{spread:.2f} EUR/MWh</span></div>',
        unsafe_allow_html=True
    )

with col2:
    st.markdown('<div class="col-header blue">📊 Přesnost modelu</div>', unsafe_allow_html=True)
    if not df_summary.empty:
        latest = df_summary.iloc[0]
        mae    = latest.get("mae_all")
        rmse   = latest.get("rmse_all")
        median = latest.get("median_abs_error")
        smape  = latest.get("smape_all_pct")
        days   = latest.get("eval_days_total", 0)

        if all(v is not None for v in [mae, rmse, median, smape]):
            st.markdown(
                f'<div class="row-item"><span class="row-name">MAE</span>'
                f'<span class="row-value" style="color:#cdd8f0">{mae:.2f} EUR/MWh</span></div>'
                f'<div class="row-item"><span class="row-name">RMSE</span>'
                f'<span class="row-value" style="color:#cdd8f0">{rmse:.2f} EUR/MWh</span></div>'
                f'<div class="row-item"><span class="row-name">Median AE</span>'
                f'<span class="row-value" style="color:#cdd8f0">{median:.2f} EUR/MWh</span></div>'
                f'<div class="row-item"><span class="row-name">SMAPE</span>'
                f'<span class="row-value" style="color:#ffd740">{smape:.1f} %</span></div>'
                f'<div class="row-item"><span class="row-name">Hodnoceno dní</span>'
                f'<span class="row-value" style="color:#8899bb">{int(days)}</span></div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown('<div style="color:#8899bb;font-size:.8rem;">Zatím nedostatek dat</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="color:#8899bb;font-size:.8rem;">Zatím nedostatek dat</div>', unsafe_allow_html=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── GRAF: FORECAST ZÍTŘEK ──────────────────────────
fig = go.Figure()
fig.add_trace(go.Bar(
    x=df_forecast["hour"],
    y=df_forecast["forecast_price"],
    name="Forecast",
    marker_color="#00e676",
    hovertemplate="Hodina %{x}:00<br><b>%{y:.2f} EUR/MWh</b>",
))

if not df_prices.empty:
    fc_date = pd.to_datetime(df_forecast["forecast_date"].iloc[0]).date()
    actual  = df_prices[pd.to_datetime(df_prices["price_date"]).dt.date == fc_date]
    if not actual.empty:
        fig.add_trace(go.Scatter(
            x=actual["hour"], y=actual["price_eur"],
            name="Skutečná cena",
            line=dict(color="#ff3d57", width=2),
            hovertemplate="Hodina %{x}:00<br><b>%{y:.2f} EUR/MWh</b>",
        ))

fig.update_layout(**base_layout("Forecast cen – zítřek [EUR/MWh]", "#00e676"))
fig.update_xaxes(
    tickmode="linear", tick0=0, dtick=1,
    ticktext=[f"{h:02d}:00" for h in range(24)],
    tickvals=list(range(24))
)
st.plotly_chart(fig, use_container_width=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── GRAF: FORECAST TRACKING ────────────────────────
st.markdown(
    '<div style="font-family:\'Courier New\',monospace;font-size:0.7rem;'
    'letter-spacing:3px;text-transform:uppercase;color:#00c8ff;'
    'border-bottom:2px solid #00c8ff;padding-bottom:6px;margin-bottom:16px;">'
    '📅 Forecast vs. Skutečnost – posledních 5 dní</div>',
    unsafe_allow_html=True
)

if not df_hist.empty and not df_prices.empty:
    df_hist["forecast_date"] = pd.to_datetime(df_hist["forecast_date"]).dt.date
    df_prices["price_date"]  = pd.to_datetime(df_prices["price_date"]).dt.date

    forecast_dates = sorted(df_hist["forecast_date"].unique())
    price_dates    = set(df_prices["price_date"].unique())
    common_dates   = sorted([d for d in forecast_dates if d in price_dates], reverse=True)[:5]

    if common_dates:
        n    = len(common_dates)
        fig2 = make_subplots(
            rows=n, cols=1,
            subplot_titles=[d.strftime("%d.%m.%Y") for d in common_dates],
            vertical_spacing=0.08,
        )

        for i, day in enumerate(common_dates, start=1):
            fc_day = df_hist[df_hist["forecast_date"] == day].sort_values("hour")
            ac_day = df_prices[df_prices["price_date"] == day].sort_values("hour")

            if not fc_day.empty:
                fig2.add_trace(go.Scatter(
                    x=fc_day["hour"], y=fc_day["forecast_price"],
                    name="Forecast",
                    line=dict(color="#00e676", width=1.5),
                    hovertemplate=f"{day.strftime('%d.%m')} %{{x}}:00<br>Forecast: <b>%{{y:.2f}} EUR</b>",
                    showlegend=(i == 1),
                ), row=i, col=1)

            if not ac_day.empty:
                fig2.add_trace(go.Scatter(
                    x=ac_day["hour"], y=ac_day["price_eur"],
                    name="Skutečnost",
                    line=dict(color="#ff3d57", width=1.5, dash="dot"),
                    hovertemplate=f"{day.strftime('%d.%m')} %{{x}}:00<br>Skutečnost: <b>%{{y:.2f}} EUR</b>",
                    showlegend=(i == 1),
                ), row=i, col=1)

            if not fc_day.empty and not ac_day.empty:
                merged = fc_day.merge(ac_day, on="hour", how="inner")
                if not merged.empty:
                    mae_day = (merged["forecast_price"] - merged["price_eur"]).abs().mean()
                    fig2.add_annotation(
                        text=f"MAE: {mae_day:.1f} EUR/MWh",
                        xref=f"x{i}", yref=f"y{i}",
                        x=23,
                        y=merged[["forecast_price", "price_eur"]].max().max(),
                        showarrow=False,
                        font=dict(size=9, color="#ffd740", family="Courier New"),
                        xanchor="right",
                    )

        fig2.update_layout(
            paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
            font=dict(color=FONT_COL, family="Courier New", size=10),
            hovermode="x unified",
            height=180 * n,
            margin=dict(l=50, r=10, t=30, b=20),
            legend=dict(bgcolor=PLOT_BG, bordercolor=GRID_COL, orientation="h", y=1.02, x=0),
        )
        for i in range(1, n + 1):
            fig2.update_xaxes(gridcolor=GRID_COL, showgrid=True, tickmode="linear", tick0=0, dtick=2, row=i, col=1)
            fig2.update_yaxes(gridcolor=GRID_COL, showgrid=True, row=i, col=1)
            fig2.layout.annotations[i-1].font.color = "#8899bb"
            fig2.layout.annotations[i-1].font.size  = 11

        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Zatím nejsou dostupná data pro porovnání forecast vs. skutečnost.")
else:
    st.info("Zatím nejsou dostupná data pro forecast tracking.")

# ── TABULKY ────────────────────────────────────────
with st.expander("📋 Hodinový forecast – detail"):
    df_show = df_forecast.copy()
    df_show["hodina"] = df_show["hour"].apply(lambda h: f"{int(h):02d}:00")
    df_show = df_show.rename(columns={
        "forecast_price": "Forecast [EUR/MWh]",
        "model_used":     "Model",
    })[["hodina", "Forecast [EUR/MWh]", "Model"]]
    st.dataframe(df_show, use_container_width=True, hide_index=True)

with st.expander("📋 Hodnocení přesnosti – posledních 30 dní"):
    if not df_eval.empty:
        st.dataframe(df_eval, use_container_width=True, hide_index=True)
    else:
        st.info("Zatím žádná hodnocení.")

st.caption("Data: ENTSO-E Transparency Platform | Model: HistGradientBoostingRegressor")
