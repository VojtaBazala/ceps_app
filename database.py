import os, sys
os.environ["DATABASE_URL"] = "postgres://uqd7goivrkoob:p51129a2d6ee93777b766769fcd20cccb30b1daa4c62b7a54f6d4cd0f7e81204b@c4pml560q9pviv.cluster-czz5s0kz4scl.eu-west-1.rds.amazonaws.com:5432/d2fi1o2fta1pfn"
sys.path.insert(0, '/content')

from database import get_engine
from sqlalchemy import text
import pandas as pd

engine = get_engine()

with engine.connect() as conn:
    # FCR přehled
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS fcr_overview (
            id              SERIAL PRIMARY KEY,
            trade_date      DATE NOT NULL,
            product_name    TEXT,
            crossborder_price FLOAT,
            cz_demand_mw    FLOAT,
            cz_price        FLOAT,
            cz_deficit_surplus FLOAT,
            UNIQUE(trade_date, product_name)
        )
    """))
    # aFRR přehled
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS afrr_overview (
            id              SERIAL PRIMARY KEY,
            trade_date      DATE NOT NULL,
            product         TEXT,
            total_marginal_price FLOAT,
            total_avg_price FLOAT,
            cz_min_price    FLOAT,
            cz_avg_price    FLOAT,
            cz_marginal_price FLOAT,
            cz_import_export FLOAT,
            cz_allocated_mw FLOAT,
            UNIQUE(trade_date, product)
        )
    """))
    # aFRR orderbook (anonymní list)
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS afrr_orderbook (
            id              SERIAL PRIMARY KEY,
            trade_date      DATE NOT NULL,
            product         TEXT,
            country         TEXT,
            capacity_price  FLOAT,
            offered_mw      FLOAT,
            allocated_mw    FLOAT,
            UNIQUE(trade_date, product, country, capacity_price, offered_mw)
        )
    """))
    conn.commit()
print("✅ Tabulky vytvořeny!")
def load_fcr_overview() -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql("""
        SELECT trade_date, product_name, crossborder_price,
               cz_demand_mw, cz_price, cz_deficit_surplus
        FROM fcr_overview
        WHERE trade_date = (SELECT MAX(trade_date) FROM fcr_overview)
        ORDER BY product_name
    """, engine)
    return df

def load_afrr_overview() -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql("""
        SELECT trade_date, product, total_marginal_price, total_avg_price,
               cz_min_price, cz_avg_price, cz_marginal_price,
               cz_import_export, cz_allocated_mw
        FROM afrr_overview
        WHERE trade_date = (SELECT MAX(trade_date) FROM afrr_overview)
        ORDER BY product
    """, engine)
    return df

def load_afrr_orderbook(product: str = None) -> pd.DataFrame:
    engine = get_engine()
    where = "WHERE trade_date = (SELECT MAX(trade_date) FROM afrr_orderbook)"
    if product:
        where += f" AND product = '{product}'"
    df = pd.read_sql(f"""
        SELECT trade_date, product, capacity_price, offered_mw, allocated_mw
        FROM afrr_orderbook
        {where}
        ORDER BY product, capacity_price
    """, engine)
    return df
