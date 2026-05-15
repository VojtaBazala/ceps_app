"""
run_pipeline.py – spouští DAM forecast pipeline a ukládá výsledky do DB
Volá se z Heroku Scheduler každý den v 7:00
"""

import os
import sys
import warnings
warnings.filterwarnings("ignore")

# Přidáme aktuální složku do path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from datetime import timedelta

# ── IMPORT PIPELINE FUNKCÍ ─────────────────────────
# Importujeme funkce z původního notebooku
# Notebook musí být uložen jako dam_forecast.py v repozitáři
try:
    from dam_forecast import (
        load_or_update_prices,
        make_daily_price_features,
        build_training_rows,
        fit_price_models,
        build_forecast_input_for_tomorrow,
        predict_tomorrow_price,
        build_bess_summary,
        evaluate_pending_forecasts,
        append_forecast_history,
        load_model_from_disk,
        save_model_to_disk,
        should_retrain_model,
        loaded_model_payload_is_compatible,
        MODEL_FILE,
        FORCE_RETRAIN,
        RETRAIN_IF_MODEL_OLDER_THAN_DAYS,
    )
    PIPELINE_AVAILABLE = True
except ImportError as e:
    print(f"⚠ Nelze importovat dam_forecast.py: {e}")
    PIPELINE_AVAILABLE = False

from database import (
    init_tables,
    save_forecast,
    save_prices,
    save_bess_summary,
    save_forecast_eval,
    load_forecast_eval,
)


def run():
    print("=" * 50)
    print(f"DAM Forecast Pipeline – {pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')}")
    print("=" * 50)

    # 1. Inicializace DB tabulek
    print("1) Inicializuji DB tabulky...")
    init_tables()

    if not PIPELINE_AVAILABLE:
        print("❌ dam_forecast.py není dostupný. Pipeline nelze spustit.")
        sys.exit(1)

    # 2. Načtení/aktualizace cen
    print("2) Načítám ceny z ENTSO-E...")
    prices_df = load_or_update_prices()
    print(f"   Ceny: {len(prices_df)} řádků, {prices_df['date'].min()} – {prices_df['date'].max()}")

    # 3. Uložení cen do DB
    print("3) Ukládám ceny do DB...")
    save_prices(prices_df)

    # 4. Evaluate pending forecasts
    print("4) Hodnotím předchozí forecasty...")
    evaluate_pending_forecasts(prices_df)

    # 5. Uložení evaluation do DB
    eval_df = load_forecast_eval(days=60)  # lokální funkce z db
    # Načteme z CSV souborů (pipeline je ukládá) a uložíme do DB
    from dam_forecast import FORECAST_EVAL_FILE
    if os.path.exists(FORECAST_EVAL_FILE):
        eval_from_file = pd.read_csv(FORECAST_EVAL_FILE)
        save_forecast_eval(eval_from_file)
        print(f"   Uloženo {len(eval_from_file)} eval řádků")

    # 6. Daily prices features
    print("5) Stavím daily price features...")
    daily_prices = make_daily_price_features(prices_df)

    # 7. Model – load nebo retrain
    print("6) Model pipeline...")
    need_retrain = FORCE_RETRAIN or should_retrain_model(MODEL_FILE, RETRAIN_IF_MODEL_OLDER_THAN_DAYS)
    loaded = None

    if not need_retrain:
        loaded = load_model_from_disk(MODEL_FILE)
        if not loaded_model_payload_is_compatible(loaded):
            print("   Nekompatibilní model, retrénuji...")
            loaded = None
            need_retrain = True

    if loaded is not None:
        price_models       = loaded["price_models"]
        price_feature_cols = loaded["price_feature_cols"]
        global_fallback    = loaded["global_fallback_model"]
        print(f"   Načten model z disku ({len(price_models)} hourly modelů)")
    else:
        print("   Trénuji nový model...")
        train_df = build_training_rows(daily_prices)
        (
            price_models,
            price_feature_cols,
            price_diag_df,
            global_fallback,
            price_oof_df,
            price_baseline_summary_df,
            price_business_metrics_df,
        ) = fit_price_models(train_df)
        save_model_to_disk(
            price_models=price_models,
            price_feature_cols=price_feature_cols,
            price_diag_df=price_diag_df,
            global_fallback_model=global_fallback,
            price_oof_df=price_oof_df,
            price_baseline_summary_df=price_baseline_summary_df,
            price_business_metrics_df=price_business_metrics_df,
            model_file=MODEL_FILE,
        )
        print(f"   Model natrénován a uložen")

    # 8. Forecast
    print("7) Generuji forecast...")
    forecast_input = build_forecast_input_for_tomorrow(daily_prices)
    forecast_df    = predict_tomorrow_price(forecast_input, price_models, price_feature_cols, global_fallback)

    if len(forecast_df) != 24:
        raise ValueError(f"Forecast nemá 24 hodin: {len(forecast_df)}")

    run_date      = pd.to_datetime(prices_df["date"].max()).date()
    forecast_date = pd.to_datetime(forecast_df["date"].iloc[0]).date()
    print(f"   Forecast pro: {forecast_date}")

    # 9. Uložení forecastu do DB
    print("8) Ukládám forecast do DB...")
    save_forecast(forecast_df, run_date, forecast_date)

    # 10. BESS summary
    print("9) Počítám BESS dispatch...")
    summary_df = build_bess_summary(forecast_df)
    save_bess_summary(summary_df)

    # 11. Append forecast history (lokální soubor pro evaluate)
    append_forecast_history(
        forecast_df=forecast_df,
        run_date=run_date,
        forecast_for_date=forecast_date,
    )

    print("=" * 50)
    print(f"✅ Pipeline dokončena: {pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')}")
    print(f"   Forecast pro: {forecast_date}")
    s = summary_df.iloc[0]
    print(f"   Profit 1 cyklus: {s['profit_1cycle_EUR']:.2f} EUR")
    print(f"   Profit 2 cykly:  {s['profit_2cycles_EUR']:.2f} EUR")
    print("=" * 50)


if __name__ == "__main__":
    run()
