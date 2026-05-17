"""
pages/1_DAM_Forecast.py – stránka s DAM forecast výsledky
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
    from database import (
        load_latest_forecast, load_prices,
        load_bess_summary_history, load_forecast_eval, load_forecast_history,
    )
    DB_OK = True
except Exception as e:
    DB_OK = False
    DB_ERROR = str(e)

st.set_page_config(page_title="DAM Forecast", page_icon="📈", layout="wide")

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
    color:#00e676; letter-spacing:3px; text-transform:uppercase; margin-bottom:0.3rem;
  }}
  .divider {{ border-top:1px solid {BORDER}; margin:0.8rem 0; }}
  .col-header {{
    font-family:'Courier New',monospace; font-size:0.7rem; letter-spacing:3px;
    text-transform:uppercase; border-bottom:2px solid; padding-bottom:6px; margin-bottom:12px;
  }}
  .col-header.green {{ border-color:#00e676; color:#00e676; }}
  .col-header.blue  {{ border-color:#00c8ff; color:#00c8ff; }}
  .row-item {{
    display:flex; justify-content:space-between; align-items:center;
    padding:5px 0; border-bottom:1px solid {BORDER}; font-family:'Courier New',monospace;
  }}
  .row-item:last-child {{ border-bottom:none; }}
  .row-name  {{ font-size:0.7rem; color:{SUBTEXT}; letter-spacing:1px; }}
  .row-name[title] {{ cursor:help; border-bottom:1px dotted {SUBTEXT}; }}
  .row-value {{ font-size:0.95rem; font-weight:700; }}
  div[data-testid="stButton"] button {{
    background:transparent !important; border:1px solid {BORDER} !important;
    color:{SUBTEXT} !important; font-size:0.8rem !important;
    padding:4px 10px !important; font-family:'Courier New',monospace !important;
  }}
  div[data-testid="stButton"] button:hover {{ border-color:#00e676 !important; color:#00e676 !important; }}
</style>
""", unsafe_allow_html=True)

def base_layout(title, color="#00e676", height=280):
    return dict(
        title=dict(text=title, font=dict(color=color, size=13, family="Courier New")),
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=LEG_COL, family="Courier New", size=11),
        hovermode="x unified",
        legend=dict(bgcolor=PLOT_BG, bordercolor=BORDER, font=dict(size=11, color=LEG_COL)),
        xaxis=dict(gridcolor=GRID_COL, showgrid=True, color=LEG_COL),
        yaxis=dict(gridcolor=GRID_COL, showgrid=True, color=LEG_COL),
        margin=dict(l=50, r=10, t=40, b=30), height=height,
    )

# ── HLAVIČKA ───────────────────────────────────────
header_l, header_r = st.columns([7, 3])
with header_l:
    st.markdown('<div class="page-title">📈 DAM Forecast</div>', unsafe_allow_html=True)
with header_r:
    nav_sp, nav_sel, nav_tema = st.columns([1, 3, 1])
    with nav_sel:
        show_nav("nav_dam")
    with nav_tema:
        if st.button(BTN_TEMA, use_container_width=True):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()

st.markdown(
    f'<div style="font-family:\'Courier New\',monospace;font-size:0.85rem;color:{TEXT};letter-spacing:1px;margin-bottom:4px;">'
    f'Predikce hodinových cen na následující den; aktualizace zpravidla do 7:30 D-1</div>',
    unsafe_allow_html=True
)
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

if not DB_OK:
    st.error(f"❌ Nepodařilo se připojit k databázi: {DB_ERROR}")
    st.stop()

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
    st.warning("⚠ Zatím nejsou k dispozici žádná data.")
    st.stop()

# ── DATUM ──────────────────────────────────────────
forecast_date_str = pd.to_datetime(df_forecast["forecast_date"].iloc[0]).strftime("%d.%m.%Y")
if "run_date" in df_forecast.columns and df_forecast["run_date"].iloc[0] is not None:
    run_date_str = pd.to_datetime(df_forecast["run_date"].iloc[0]).strftime("%d.%m.%Y %H:%M")
else:
    run_date_str = "—"

st.markdown(
    f'<div style="font-family:\'Courier New\',monospace;font-size:0.8rem;color:{SUBTEXT};">'
    f'Forecast pro: <span style="color:#00e676">{forecast_date_str}</span>'
    f' &nbsp;|&nbsp; Vytvořeno: <span style="color:#00e676">{run_date_str}</span></div>',
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
        f'<div class="row-item"><span class="row-name">Průměr (baseload)</span><span class="row-value" style="color:#00e676">{avg_price:.2f} EUR/MWh</span></div>'
        f'<div class="row-item"><span class="row-name">Min – hodina {int(min_row["hour"]):02d}:00</span><span class="row-value" style="color:#13b8f0">{min_row["forecast_price"]:.2f} EUR/MWh</span></div>'
        f'<div class="row-item"><span class="row-name">Max – hodina {int(max_row["hour"]):02d}:00</span><span class="row-value" style="color:#ff3d57">{max_row["forecast_price"]:.2f} EUR/MWh</span></div>'
        f'<div class="row-item"><span class="row-name">Spread</span><span class="row-value" style="color:#ffd740">{spread:.2f} EUR/MWh</span></div>',
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
                f'<div class="row-item"><span class="row-name" title="Průměrná absolutní chyba forecastu – o kolik EUR/MWh se forecast průměrně mýlí">MAE ⓘ</span><span class="row-value" style="color:{TEXT}">{mae:.2f} EUR/MWh</span></div>'
                f'<div class="row-item"><span class="row-name" title="Odmocnina průměru čtverců chyb – penalizuje velké odchylky více než MAE">RMSE ⓘ</span><span class="row-value" style="color:{TEXT}">{rmse:.2f} EUR/MWh</span></div>'
                f'<div class="row-item"><span class="row-name" title="Střední absolutní chyba – méně citlivá na extrémní výchylky než MAE">Median AE ⓘ</span><span class="row-value" style="color:{TEXT}">{median:.2f} EUR/MWh</span></div>'
                f'<div class="row-item"><span class="row-name" title="Průměrná procentuální chyba – relativní přesnost forecastu vůči skutečné ceně">SMAPE ⓘ</span><span class="row-value" style="color:#ffd740">{smape:.1f} %</span></div>'
                f'<div class="row-item"><span class="row-name" title="Počet dní pro které máme jak forecast tak skutečnou cenu">Hodnoceno dní ⓘ</span><span class="row-value" style="color:{SUBTEXT}">{int(days)}</span></div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(f'<div style="color:{SUBTEXT};font-size:.8rem;">Zatím nedostatek dat</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div style="color:{SUBTEXT};font-size:.8rem;">Zatím nedostatek dat</div>', unsafe_allow_html=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── GRAF: FORECAST ─────────────────────────────────
fig = go.Figure()
fig.add_trace(go.Bar(
    x=df_forecast["hour"], y=df_forecast["forecast_price"],
    name="Forecast", marker_color="#00e676",
    hovertemplate="Hodina %{x}:00<br><b>%{y:.2f} EUR/MWh</b>",
))
if not df_prices.empty:
    fc_date = pd.to_datetime(df_forecast["forecast_date"].iloc[0]).date()
    actual  = df_prices[pd.to_datetime(df_prices["price_date"]).dt.date == fc_date]
    if not actual.empty:
        fig.add_trace(go.Scatter(
            x=actual["hour"], y=actual["price_eur"],
            name="Skutečná cena", line=dict(color="#ff3d57", width=2),
            hovertemplate="Hodina %{x}:00<br><b>%{y:.2f} EUR/MWh</b>",
        ))
fig.update_layout(**base_layout("Forecast cen – zítřek [EUR/MWh]", "#00e676"))
fig.update_xaxes(tickmode="linear", tick0=0, dtick=1,
    ticktext=[f"{h:02d}:00" for h in range(24)], tickvals=list(range(24)))
st.plotly_chart(fig, use_container_width=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ── FORECAST TRACKING – 4 dny, 2x2 grid ───────────
st.markdown(
    f'<div style="font-family:\'Courier New\',monospace;font-size:0.7rem;letter-spacing:3px;'
    f'text-transform:uppercase;color:#00c8ff;border-bottom:2px solid #00c8ff;'
    f'padding-bottom:6px;margin-bottom:16px;">📅 Forecast vs. Skutečnost – poslední 4 dny</div>',
    unsafe_allow_html=True
)

if not df_hist.empty and not df_prices.empty:
    df_hist["forecast_date"] = pd.to_datetime(df_hist["forecast_date"]).dt.date
    df_prices["price_date"]  = pd.to_datetime(df_prices["price_date"]).dt.date
    common_dates = sorted(
        [d for d in df_hist["forecast_date"].unique() if d in set(df_prices["price_date"].unique())],
        reverse=True
    )[:4]

    if common_dates:
        row_col = {1:(1,1), 2:(1,2), 3:(2,1), 4:(2,2)}
        fig2 = make_subplots(
            rows=2, cols=2,
            subplot_titles=[d.strftime("%d.%m.%Y") for d in common_dates],
            vertical_spacing=0.15,
            horizontal_spacing=0.08,
        )
        for i, day in enumerate(common_dates, start=1):
            r_i, c_i = row_col[i]
            fc_day = df_hist[df_hist["forecast_date"]==day].sort_values("hour")
            ac_day = df_prices[df_prices["price_date"]==day].sort_values("hour")
            if not fc_day.empty:
                fig2.add_trace(go.Scatter(
                    x=fc_day["hour"], y=fc_day["forecast_price"],
                    name="Forecast", line=dict(color="#00e676", width=1.5),
                    hovertemplate=f"{day.strftime('%d.%m')} %{{x}}:00<br>Forecast: <b>%{{y:.2f}} EUR</b>",
                    showlegend=(i==1),
                ), row=r_i, col=c_i)
            if not ac_day.empty:
                fig2.add_trace(go.Scatter(
                    x=ac_day["hour"], y=ac_day["price_eur"],
                    name="Skutečnost", line=dict(color="#ff3d57", width=1.5, dash="dot"),
                    hovertemplate=f"{day.strftime('%d.%m')} %{{x}}:00<br>Skutečnost: <b>%{{y:.2f}} EUR</b>",
                    showlegend=(i==1),
                ), row=r_i, col=c_i)
            if not fc_day.empty and not ac_day.empty:
                merged = fc_day.merge(ac_day, on="hour", how="inner")
                if not merged.empty:
                    mae_day = (merged["forecast_price"]-merged["price_eur"]).abs().mean()
                    ax = "" if i == 1 else str(i)
                    fig2.add_annotation(
                        text=f"MAE: {mae_day:.1f} EUR/MWh",
                        xref=f"x{ax}", yref=f"y{ax}", x=23,
                        y=merged[["forecast_price","price_eur"]].max().max(),
                        showarrow=False,
                        font=dict(size=9, color="#ffd740", family="Courier New"),
                        xanchor="right",
                    )
        fig2.update_layout(
            paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
            font=dict(color=LEG_COL, family="Courier New", size=11),
            hovermode="x unified", height=420,
            margin=dict(l=50, r=10, t=40, b=20),
            legend=dict(bgcolor=PLOT_BG, bordercolor=BORDER, font=dict(size=11, color=LEG_COL), orientation="h", y=1.05, x=0),
        )
        for i, (r_i, c_i) in row_col.items():
            if i <= len(common_dates):
                fig2.update_xaxes(gridcolor=GRID_COL, showgrid=True, color=LEG_COL, tickmode="linear", tick0=0, dtick=4, row=r_i, col=c_i)
                fig2.update_yaxes(gridcolor=GRID_COL, showgrid=True, color=LEG_COL, row=r_i, col=c_i)
        for j in range(len(common_dates)):
            fig2.layout.annotations[j].font.color = SUBTEXT
            fig2.layout.annotations[j].font.size  = 11
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Zatím nejsou dostupná data pro porovnání.")
else:
    st.info("Zatím nejsou dostupná data pro forecast tracking.")

with st.expander("📋 Hodinový forecast – detail"):
    df_show = df_forecast.copy()
    df_show["hodina"] = df_show["hour"].apply(lambda h: f"{int(h):02d}:00")
    df_show = df_show.rename(columns={"forecast_price":"Forecast [EUR/MWh]","model_used":"Model"})[["hodina","Forecast [EUR/MWh]","Model"]]
    st.dataframe(df_show, use_container_width=True, hide_index=True)

with st.expander("📋 Hodnocení přesnosti – posledních 30 dní"):
    if not df_eval.empty:
        st.dataframe(df_eval, use_container_width=True, hide_index=True)
    else:
        st.info("Zatím žádná hodnocení.")

st.markdown(
    '<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400&display=swap" rel="stylesheet">',
    unsafe_allow_html=True
)
st.markdown(
    f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:4px;">'
    f'<span style="font-size:0.75rem;color:{SUBTEXT};">Data: ENTSO-E Transparency Platform | Model: HistGradientBoostingRegressor</span>'
    f'<span style="font-size:0.75rem;color:#8899bb;font-style:italic;">oldrich by claude</span>'
    f'<span style="font-family:\'Cinzel\',serif;font-size:0.85rem;color:#8899bb;letter-spacing:2px;">Festina lente</span>'
    f'</div>',
    unsafe_allow_html=True
)
