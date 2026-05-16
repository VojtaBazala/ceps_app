"""
database.py – pomocné funkce pro práci s PostgreSQL na Heroku
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text

# ── PŘIPOJENÍ ──────────────────────────────────────
def get_engine():
    url = os.environ.get("DATABASE_URL", "")
    # Heroku používá postgres:// ale SQLAlchemy vyžaduje postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url)


# ── INICIALIZACE TABULEK ───────────────────────────
def init_tables():
    engine = get_engine()
    with engine.connect() as conn:

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS dam_forecast (
            id              SERIAL PRIMARY KEY,
            run_date        DATE NOT NULL,
            forecast_date   DATE NOT NULL,
            hour            INTEGER NOT NULL,
            forecast_price  FLOAT,
            model_used      TEXT,
            created_at      TIMESTAMP DEFAULT NOW(),
            UNIQUE(run_date, forecast_date, hour)
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS dam_prices (
            id          SERIAL PRIMARY KEY,
            price_date  DATE NOT NULL,
            hour        INTEGER NOT NULL,
            price_eur   FLOAT,
            created_at  TIMESTAMP DEFAULT NOW(),
            UNIQUE(price_date, hour)
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS dam_bess_summary (
            id                      SERIAL PRIMARY KEY,
            forecast_date           DATE NOT NULL UNIQUE,
            min_hour                INTEGER,
            min_price               FLOAT,
            max_hour                INTEGER,
            max_price               FLOAT,
            spread                  FLOAT,
            profit_1cycle_eur       FLOAT,
            profit_2cycles_eur      FLOAT,
            profit_3cycles_eur      FLOAT,
            mae_all                 FLOAT,
            rmse_all                FLOAT,
            median_abs_error        FLOAT,
            smape_all_pct           FLOAT,
            eval_rows_total         INTEGER,
            eval_days_total         INTEGER,
            last_eval_date          DATE,
            created_at              TIMESTAMP DEFAULT NOW()
        )
        """))

        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS dam_forecast_eval (
            id                      SERIAL PRIMARY KEY,
            forecast_run_date       DATE,
            forecast_for_date       DATE,
            hour                    INTEGER,
            forecast_price          FLOAT,
            actual_price            FLOAT,
            error                   FLOAT,
            abs_error               FLOAT,
            smape_pct               FLOAT,
            created_at              TIMESTAMP DEFAULT NOW(),
            UNIQUE(forecast_run_date, forecast_for_date, hour)
        )
        """))

        conn.commit()
    print("DB tabulky inicializovány.")


# ── UKLÁDÁNÍ DAT ───────────────────────────────────
def save_forecast(forecast_df: pd.DataFrame, run_date, forecast_date):
    engine = get_engine()
    rows = []
    for _, r in forecast_df.iterrows():
        rows.append({
            "run_date":       str(run_date),
            "forecast_date":  str(forecast_date),
            "hour":           int(r["hour"]),
            "forecast_price": float(r["forecast_price_EUR_MWh"]),
            "model_used":     str(r.get("model_used", "unknown")),
        })
    df = pd.DataFrame(rows)
    with engine.connect() as conn:
        for _, row in df.iterrows():
            conn.execute(text("""
                INSERT INTO dam_forecast
                    (run_date, forecast_date, hour, forecast_price, model_used)
                VALUES
                    (:run_date, :forecast_date, :hour, :forecast_price, :model_used)
                ON CONFLICT (run_date, forecast_date, hour)
                DO UPDATE SET
                    forecast_price = EXCLUDED.forecast_price,
                    model_used     = EXCLUDED.model_used
            """), row.to_dict())
        conn.commit()
    print(f"Forecast uložen: {forecast_date} ({len(df)} hodin)")


def save_prices(prices_df: pd.DataFrame):
    engine = get_engine()
    rows = []
    for _, r in prices_df.iterrows():
        rows.append({
            "price_date": str(r["date"]),
            "hour":       int(r["hour"]),
            "price_eur":  float(r["price_EUR_MWh"]),
        })
    df = pd.DataFrame(rows)
    with engine.connect() as conn:
        for _, row in df.iterrows():
            conn.execute(text("""
                INSERT INTO dam_prices (price_date, hour, price_eur)
                VALUES (:price_date, :hour, :price_eur)
                ON CONFLICT (price_date, hour)
                DO UPDATE SET price_eur = EXCLUDED.price_eur
            """), row.to_dict())
        conn.commit()
    print(f"Ceny uloženy: {len(df)} řádků")


def save_bess_summary(summary_df: pd.DataFrame):
    engine = get_engine()
    s = summary_df.iloc[0]
    row = {
        "forecast_date":      str(s["forecast_date"]),
        "min_hour":           int(s["min_hour_forecast"]),
        "min_price":          float(s["min_price_forecast_EUR_MWh"]),
        "max_hour":           int(s["max_hour_forecast"]),
        "max_price":          float(s["max_price_forecast_EUR_MWh"]),
        "spread":             float(s["forecast_spread_EUR_MWh"]),
        "profit_1cycle_eur":  float(s["profit_1cycle_EUR"]),
        "profit_2cycles_eur": float(s["profit_2cycles_EUR"]),
        "profit_3cycles_eur": float(s["profit_3cycles_EUR"]),
        "mae_all":            float(s["mae_all_EUR_MWh"]) if s["mae_all_EUR_MWh"] else None,
        "rmse_all":           float(s["rmse_all_EUR_MWh"]) if s["rmse_all_EUR_MWh"] else None,
        "median_abs_error":   float(s["median_abs_error_all_EUR_MWh"]) if s["median_abs_error_all_EUR_MWh"] else None,
        "smape_all_pct":      float(s["smape_all_pct"]) if s["smape_all_pct"] else None,
        "eval_rows_total":    int(s["eval_rows_total"]) if s["eval_rows_total"] else 0,
        "eval_days_total":    int(s["eval_days_total"]) if s["eval_days_total"] else 0,
        "last_eval_date":     str(s["last_eval_date"]) if s["last_eval_date"] else None,
    }
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO dam_bess_summary
                (forecast_date, min_hour, min_price, max_hour, max_price, spread,
                 profit_1cycle_eur, profit_2cycles_eur, profit_3cycles_eur,
                 mae_all, rmse_all, median_abs_error, smape_all_pct,
                 eval_rows_total, eval_days_total, last_eval_date)
            VALUES
                (:forecast_date, :min_hour, :min_price, :max_hour, :max_price, :spread,
                 :profit_1cycle_eur, :profit_2cycles_eur, :profit_3cycles_eur,
                 :mae_all, :rmse_all, :median_abs_error, :smape_all_pct,
                 :eval_rows_total, :eval_days_total, :last_eval_date)
            ON CONFLICT (forecast_date)
            DO UPDATE SET
                min_hour           = EXCLUDED.min_hour,
                min_price          = EXCLUDED.min_price,
                max_hour           = EXCLUDED.max_hour,
                max_price          = EXCLUDED.max_price,
                spread             = EXCLUDED.spread,
                profit_1cycle_eur  = EXCLUDED.profit_1cycle_eur,
                profit_2cycles_eur = EXCLUDED.profit_2cycles_eur,
                profit_3cycles_eur = EXCLUDED.profit_3cycles_eur,
                mae_all            = EXCLUDED.mae_all,
                rmse_all           = EXCLUDED.rmse_all,
                median_abs_error   = EXCLUDED.median_abs_error,
                smape_all_pct      = EXCLUDED.smape_all_pct,
                eval_rows_total    = EXCLUDED.eval_rows_total,
                eval_days_total    = EXCLUDED.eval_days_total,
                last_eval_date     = EXCLUDED.last_eval_date
        """), row)
        conn.commit()
    print(f"BESS summary uložen: {s['forecast_date']}")


def save_forecast_eval(eval_df: pd.DataFrame):
    if eval_df.empty:
        return
    engine = get_engine()
    with engine.connect() as conn:
        for _, r in eval_df.iterrows():
            try:
                conn.execute(text("""
                    INSERT INTO dam_forecast_eval
                        (forecast_run_date, forecast_for_date, hour,
                         forecast_price, actual_price, error, abs_error, smape_pct)
                    VALUES
                        (:forecast_run_date, :forecast_for_date, :hour,
                         :forecast_price, :actual_price, :error, :abs_error, :smape_pct)
                    ON CONFLICT (forecast_run_date, forecast_for_date, hour)
                    DO UPDATE SET
                        actual_price   = EXCLUDED.actual_price,
                        error          = EXCLUDED.error,
                        abs_error      = EXCLUDED.abs_error,
                        smape_pct      = EXCLUDED.smape_pct
                """), {
                    "forecast_run_date": str(r.get("forecast_run_date")),
                    "forecast_for_date": str(r.get("forecast_for_date")),
                    "hour":              int(r.get("hour", 0)),
                    "forecast_price":    float(r.get("forecast_price_EUR_MWh", 0)),
                    "actual_price":      float(r.get("actual_price_EUR_MWh", 0)) if r.get("actual_price_EUR_MWh") else None,
                    "error":             float(r.get("error_EUR_MWh", 0)) if r.get("error_EUR_MWh") else None,
                    "abs_error":         float(r.get("abs_error_EUR_MWh", 0)) if r.get("abs_error_EUR_MWh") else None,
                    "smape_pct":         float(r.get("smape_pct", 0)) if r.get("smape_pct") else None,
                })
            except Exception:
                pass
        conn.commit()


# ── ČTENÍ DAT ──────────────────────────────────────
def load_latest_forecast() -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql("""
        SELECT run_date, forecast_date, hour, forecast_price, model_used
        FROM dam_forecast
        WHERE forecast_date = (SELECT MAX(forecast_date) FROM dam_forecast)
        ORDER BY hour
    """, engine)
    return df


def load_forecast_history(days: int = 30) -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql(f"""
        SELECT run_date, forecast_date, hour, forecast_price
        FROM dam_forecast
        WHERE forecast_date >= CURRENT_DATE - INTERVAL '{days} days'
        ORDER BY forecast_date, hour
    """, engine)
    return df


def load_prices(days: int = 30) -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql(f"""
        SELECT price_date, hour, price_eur
        FROM dam_prices
        WHERE price_date >= CURRENT_DATE - INTERVAL '{days} days'
        ORDER BY price_date, hour
    """, engine)
    return df


def load_bess_summary_history(days: int = 30) -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql(f"""
        SELECT *
        FROM dam_bess_summary
        WHERE forecast_date >= CURRENT_DATE - INTERVAL '{days} days'
        ORDER BY forecast_date DESC
    """, engine)
    return df


def load_forecast_eval(days: int = 30) -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql(f"""
        SELECT *
        FROM dam_forecast_eval
        WHERE forecast_for_date >= CURRENT_DATE - INTERVAL '{days} days'
        ORDER BY forecast_for_date DESC, hour
    """, engine)
    return df
