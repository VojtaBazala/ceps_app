# ceps_app – PROJECT STATUS

## Poslední aktualizace
2026-05-17

---

## Deployment
- **Platforma:** Heroku
- **Spuštění:** `streamlit run CEPS_online.py` (viz Procfile)
- **DB:** PostgreSQL (sdílená s flso_automation — stejný Heroku DB)

---

## Struktura repozitáře

```
ceps_app/
├── CEPS_online.py          # Hlavní stránka — ČEPS online (frekvence, SVR, cena RE)
├── database.py             # Všechny DB funkce (get_engine, load_*, save_*)
├── navigation.py           # Centrální navigace mezi stránkami
├── run_pipeline.py         # (pipeline skript — obsah neznámý)
├── pages/
│   ├── 1_DAM_Forecast.py   # DAM forecast + BESS analýza
│   ├── 2_mFRR_Orderbook.py # mFRR+ a mFRR- orderbook
│   └── 3_FCR_aFRR.py       # FCR a aFRR výsledky tendrů
├── .streamlit/config.toml
├── requirements.txt
└── Procfile
```

---

## Stránky a jejich stav

### ČEPS online (`CEPS_online.py`) ✅
- Live data z ČEPS SOAP API (frekvence, SVR aktivace, aktuální cena RE)
- Auto-refresh každých 60s
- Dark/light mode
- Graf frekvence, SVR bar chart, cena RE line chart
- Footer: `Ora et labora` (Cinzel font)

### DAM Forecast (`pages/1_DAM_Forecast.py`) ✅
- Zobrazuje forecast cen DAM z DB tabulky `dam_forecast`
- BESS analýza (profit 1/2/3 cykly)
- Forecast evaluation (MAE, RMSE, SMAPE)
- Data z tabulek: `dam_forecast`, `dam_prices`, `dam_bess_summary`, `dam_forecast_eval`

### mFRR Orderbook (`pages/2_mFRR_Orderbook.py`) ✅
- mFRR+ (zelená) a mFRR- (červená) orderbook nejnovějšího dne
- Data z tabulek: `mfrr_orderbook`, `mfrr_minus_orderbook`

### FCR & aFRR (`pages/3_FCR_aFRR.py`) ✅
- FCR výsledky tendrů + aFRR overview + aFRR orderbook CZ
- Data z tabulek: `fcr_overview`, `afrr_overview`, `afrr_orderbook`

---

## Databázové tabulky (čtení)

| Tabulka | Plněna z |
|---------|----------|
| `fcr_overview` | flso_automation / fcr_download.py |
| `afrr_overview` | flso_automation / afrr_download.py |
| `afrr_orderbook` | flso_automation / afrr_download.py |
| `mfrr_orderbook` | flso_automation / mfrr_plus_download.py |
| `mfrr_minus_orderbook` | flso_automation / mfrr_minus_download.py |
| `dam_forecast` | run_pipeline.py (obsah neznámý) |
| `dam_prices` | run_pipeline.py |
| `dam_bess_summary` | run_pipeline.py |
| `dam_forecast_eval` | run_pipeline.py |

---

## Design systém
- Dark mode default: `#0a0e1a` background, `#00c8ff` modrá, `#00e676` zelená, `#ffd740` žlutá, `#ff3d57` červená
- Font: `Courier New` monospace všude
- Navigace: selectbox v pravém horním rohu každé stránky
- Téma přepínač: ☀️/🌙 tlačítko

---

## TODO / otevřené otázky
- [ ] Obsah `run_pipeline.py` — jak se spouští DAM forecast? Manuálně / GitHub Actions?
- [ ] Jsou všechny stránky funkční na produkci?
- [ ] Návrh nových stránek / rozšíření dashboardu

---

## Poznámky
- `database.py` je sdílený s flso_automation (GitHub Actions ho stahuje přes wget)
- Latin motto na ČEPS online: **Ora et labora** (bylo Carpe diem, hora ruit — změněno 2026-05-17)
