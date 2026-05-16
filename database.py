def load_mfrr_minus_orderbook() -> pd.DataFrame:
    engine = get_engine()
    df = pd.read_sql("""
        SELECT trade_date, product_type, position, quantity_mw, price_eur_mw, cum_quantity_mw
        FROM mfrr_minus_orderbook
        WHERE trade_date = (SELECT MAX(trade_date) FROM mfrr_minus_orderbook)
          AND position = 1
        ORDER BY price_eur_mw ASC, cum_quantity_mw ASC
    """, engine)
    return df
