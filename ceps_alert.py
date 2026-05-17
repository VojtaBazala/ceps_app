"""
ceps_alert.py
Kontroluje ČEPS data a posílá email alertů při překročení thresholdů.
Spouštěno přes GitHub Actions každých 5 minut.

Alerty:
  FREKVENCE:
    - aktuální Hz mimo rozsah 49.85 – 50.15
    - delta 1h > ±0.10 MWh
    - delta 4h > ±0.20 MWh
    - delta 8h > ±0.40 MWh

  CENA RE:
    - jakákoliv položka > 500 nebo < -100 EUR/MWh

Cooldown: 1 hodina na alert_type (uloženo v DB)
"""

import os
import sys
import smtplib
import requests
import pytz
import pandas as pd
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from zeep import Client
from zeep.transports import Transport
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    EMAIL_RECIPIENTS,
    FREQ_MIN, FREQ_MAX,
    DELTA_1H_MAX, DELTA_4H_MAX, DELTA_8H_MAX,
    CENA_MAX, CENA_MIN,
    ALERT_COOLDOWN_HOURS,
)

# ── KONFIGURACE ────────────────────────────────────
DB_URL         = os.environ.get("DATABASE_URL", "")
GMAIL_USER     = "oldrich.bazala@gmail.com"
GMAIL_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
EMAIL_TO       = ", ".join(EMAIL_RECIPIENTS)
COOLDOWN_HOURS = ALERT_COOLDOWN_HOURS

WSDL = "https://vip-prod-service-00-azapp.azurewebsites.net/_layouts/cepsdata.asmx?WSDL"
NS   = "https://www.ceps.cz/CepsData/StructuredData/1.0"
TZ   = pytz.timezone("Europe/Prague")

if not DB_URL:
    raise ValueError("DATABASE_URL není nastavena!")
if not GMAIL_PASSWORD:
    raise ValueError("GMAIL_APP_PASSWORD není nastavena!")

engine = create_engine(DB_URL.replace("postgres://", "postgresql://", 1))

# ── DB: alert_log tabulka ──────────────────────────
def init_alert_log():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alert_log (
                id          SERIAL PRIMARY KEY,
                alert_type  TEXT NOT NULL,
                sent_at     TIMESTAMP NOT NULL,
                message     TEXT
            )
        """))
        conn.commit()


def can_send_alert(alert_type: str) -> bool:
    """Vrátí True pokud od posledního alertu tohoto typu uplynula alespoň 1 hodina."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT sent_at FROM alert_log
                WHERE alert_type = :t
                ORDER BY sent_at DESC
                LIMIT 1
            """), {"t": alert_type})
            row = result.fetchone()
        if row is None:
            return True
        last = row[0]
        if last.tzinfo is None:
            last = pytz.utc.localize(last)
        return datetime.now(pytz.utc) - last > timedelta(hours=COOLDOWN_HOURS)
    except Exception:
        return True


def log_alert(alert_type: str, message: str):
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO alert_log (alert_type, sent_at, message)
            VALUES (:t, :s, :m)
        """), {"t": alert_type, "s": datetime.now(pytz.utc), "m": message})
        conn.commit()


# ── EMAIL ──────────────────────────────────────────
def send_alert_email(subject: str, body: str):
    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, EMAIL_TO, msg.as_string())
    print(f"Alert odeslán: {subject}")


# ── ČEPS API ───────────────────────────────────────
def xml_na_df(result):
    items = result.findall(f"{{{NS}}}data/{{{NS}}}item")
    if not items:
        items = result.findall("data/item")
    radky = []
    for item in items:
        radek = {"cas": item.get("date")}
        for k, v in item.attrib.items():
            if k != "date":
                try:    radek[k] = float(v)
                except: radek[k] = 0.0
        radky.append(radek)
    if not radky:
        return pd.DataFrame()
    df = pd.DataFrame(radky)
    df["cas"] = pd.to_datetime(df["cas"], utc=True).dt.tz_convert("Europe/Prague")
    return df


def nazvy_serii(result):
    els = result.findall(f"{{{NS}}}series/{{{NS}}}serie")
    if not els:
        els = result.findall("series/serie")
    return {s.get("id"): s.get("name") for s in els}


def vypocti_delty(df):
    if df.empty or "value1" not in df.columns:
        return {"1h": None, "4h": None, "8h": None}
    df = df.copy()
    df["delta_min"] = (50.0 - df["value1"]) / 0.2 / 60.0
    delty = {}
    for hodiny, label in [(1, "1h"), (4, "4h"), (8, "8h")]:
        pocet = hodiny * 60
        if len(df) >= pocet:
            delty[label] = df["delta_min"].iloc[-pocet:].sum()
        elif len(df) > 0:
            delty[label] = df["delta_min"].sum()
        else:
            delty[label] = None
    return delty


def stahni_data():
    now_local = datetime.now(TZ)
    now       = now_local.replace(tzinfo=None)
    pulnoc    = now.replace(hour=0, minute=0, second=0, microsecond=0)
    date_from = min(pulnoc, now - timedelta(hours=8))
    date_to   = now

    session = requests.Session()
    client  = Client(WSDL, transport=Transport(session=session))

    r_freq = client.service.Frekvence(dateFrom=date_from, dateTo=date_to)
    r_cena = client.service.AktualniCenaRE(dateFrom=date_from, dateTo=date_to)

    return {
        "freq_df":    xml_na_df(r_freq),
        "cena_df":    xml_na_df(r_cena),
        "cena_nazvy": nazvy_serii(r_cena),
    }


# ── HLAVNÍ LOGIKA ──────────────────────────────────
def main():
    init_alert_log()

    print(f"ČEPS alert check: {datetime.now(TZ).strftime('%d.%m.%Y %H:%M:%S')}")

    try:
        data = stahni_data()
    except Exception as e:
        print(f"Chyba při stahování dat: {e}")
        sys.exit(0)  # Nezabijeme workflow, jen přeskočíme

    df_freq    = data["freq_df"]
    df_cena    = data["cena_df"]
    cena_nazvy = data["cena_nazvy"]

    now_str = datetime.now(TZ).strftime("%d.%m.%Y %H:%M:%S")

    # ── ALERT 1: Aktuální frekvence ────────────────
    if not df_freq.empty:
        freq_last = df_freq["value1"].iloc[-1]
        print(f"Frekvence aktuální: {freq_last:.3f} Hz")

        if freq_last < FREQ_MIN or freq_last > FREQ_MAX:
            alert_type = "freq_actual"
            direction  = "NÍZKÁ" if freq_last < FREQ_MIN else "VYSOKÁ"
            msg = (
                f"⚡ ALERT – Frekvence {direction}\n\n"
                f"Aktuální hodnota: {freq_last:.3f} Hz\n"
                f"Povolený rozsah: {FREQ_MIN} – {FREQ_MAX} Hz\n"
                f"Čas: {now_str}"
            )
            if can_send_alert(alert_type):
                send_alert_email(f"⚡ ČEPS ALERT – Frekvence {direction} ({freq_last:.3f} Hz)", msg)
                log_alert(alert_type, msg)
            else:
                print(f"Alert {alert_type} v cooldownu, přeskočeno")

    # ── ALERT 2: Delta frekvence ───────────────────
    if not df_freq.empty:
        delty = vypocti_delty(df_freq)
        thresholdy = {"1h": DELTA_1H_MAX, "4h": DELTA_4H_MAX, "8h": DELTA_8H_MAX}

        for label, threshold in thresholdy.items():
            val = delty.get(label)
            if val is None:
                continue
            print(f"Delta {label}: {val:+.4f} MWh (threshold ±{threshold})")
            if abs(val) > threshold:
                alert_type = f"freq_delta_{label}"
                direction  = "kladná" if val > 0 else "záporná"
                msg = (
                    f"⚡ ALERT – Delta frekvence {label}\n\n"
                    f"Kumulativní odchylka za {label}: {val:+.4f} MWh\n"
                    f"Threshold: ±{threshold} MWh\n"
                    f"Aktuální frekvence: {df_freq['value1'].iloc[-1]:.3f} Hz\n"
                    f"Čas: {now_str}"
                )
                if can_send_alert(alert_type):
                    send_alert_email(f"⚡ ČEPS ALERT – Delta {label} = {val:+.4f} MWh", msg)
                    log_alert(alert_type, msg)
                else:
                    print(f"Alert {alert_type} v cooldownu, přeskočeno")

    # ── ALERT 3: Cena RE ───────────────────────────
    if not df_cena.empty:
        for vid, vname in cena_nazvy.items():
            if vid not in df_cena.columns:
                continue
            cena_last = df_cena[vid].iloc[-1]
            print(f"Cena RE {vname}: {cena_last:.2f} EUR/MWh")

            if cena_last > CENA_MAX or cena_last < CENA_MIN:
                alert_type = f"cena_{vid}"
                direction  = "VYSOKÁ" if cena_last > CENA_MAX else "ZÁPORNÁ/NÍZKÁ"
                msg = (
                    f"💶 ALERT – Cena RE {direction}\n\n"
                    f"Produkt: {vname}\n"
                    f"Aktuální cena: {cena_last:.2f} EUR/MWh\n"
                    f"Threshold: > {CENA_MAX} nebo < {CENA_MIN} EUR/MWh\n"
                    f"Čas: {now_str}"
                )
                if can_send_alert(alert_type):
                    send_alert_email(f"💶 ČEPS ALERT – Cena RE {direction} ({cena_last:.2f} EUR/MWh)", msg)
                    log_alert(alert_type, msg)
                else:
                    print(f"Alert {alert_type} v cooldownu, přeskočeno")

    print("Check dokončen.")


if __name__ == "__main__":
    main()
