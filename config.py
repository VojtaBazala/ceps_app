# ══════════════════════════════════════════════════
# config.py – centrální konfigurace
# ══════════════════════════════════════════════════

# ── PŘÍJEMCI EMAILŮ ───────────────────────────────
# Přidej nebo odeber emailové adresy podle potřeby.

EMAIL_RECIPIENTS = [
    "oldrich@bhfund.eu",
    # "dalsi@email.cz",
]


# ── ALERT THRESHOLDY – FREKVENCE ──────────────────

# Aktuální frekvence mimo tento rozsah → alert
FREQ_MIN = 49.85   # Hz
FREQ_MAX = 50.15   # Hz

# Kumulativní odchylka kapacity 1 MW BESS
DELTA_1H_MAX = 0.10   # MWh za 1 hodinu
DELTA_4H_MAX = 0.20   # MWh za 4 hodiny
DELTA_8H_MAX = 0.40   # MWh za 8 hodin


# ── ALERT THRESHOLDY – CENA RE ────────────────────

# Jakákoliv položka ceny RE mimo tento rozsah → alert
CENA_MAX =  500.0   # EUR/MWh
CENA_MIN = -100.0   # EUR/MWh


# ── COOLDOWN ──────────────────────────────────────
# Minimální počet hodin mezi dvěma alerty stejného typu
ALERT_COOLDOWN_HOURS = 1
