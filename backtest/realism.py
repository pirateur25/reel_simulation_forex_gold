# backtest/realism.py — « couche réalisme » commune aux deux stratégies :
#  1) coûts par actif (spread + commission) issus des spreads FTMO relevés, multipliés par COST_MULT (spreads réels > spread minimal affiché) ;
#  2) fermeture de TOUTES les positions avant le week-end (vendredi 20:30 UTC) et annulation des ordres limites dès 19:30 ;
#  3) blocage des entrées autour des annonces majeures (calendrier APPROXIMATIF : NFP + FOMC ; remplaçable par un vrai calendrier CSV) ;
#  4) levier maximum par classe d'actif.
import numpy as np
import pandas as pd

# spread affiché (unités de prix, snapshot FTMO), prix de référence du snapshot, commission par ordre en unités de prix (2,5 $ par lot et par sens)
_USD = {"JPY": 157.96, "CHF": 0.829, "CAD": 1.405, "GBP": 1 / 1.3306, "USD": 1.0}
SPEC = {  # symbole: (spread, prix_ref, devise de cotation, commission % par sens, classe)
    "EURUSD": (0.00003, 1.113, "USD", None, "fx"), "GBPUSD": (0.0001, 1.3306, "USD", None, "fx"), "USDJPY": (0.005, 157.96, "JPY", None, "fx"),
    "USDCHF": (0.00006, 0.829, "CHF", None, "fx"), "AUDUSD": (0.00006, 0.7027, "USD", None, "fx"), "NZDUSD": (0.00004, 0.5683, "USD", None, "fx"),
    "USDCAD": (0.00008, 1.405, "CAD", None, "fx"), "EURGBP": (0.00008, 0.8365, "GBP", None, "fx"), "GBPJPY": (0.030, 210.17, "JPY", None, "fx"),
    "EURJPY": (0.020, 175.8, "JPY", None, "fx"),   # EURJPY absent des captures : spread supposé
    "XAUUSD": (0.46, 4062.0, "USD", 0.0014, "metal"), "XAGUSD": (0.051, 54.45, "USD", 0.0014, "metal"),
    "US30": (2.38, 52405.0, "USD", 0.0, "index"), "GER40": (3.33, 25614.0, "USD", 0.0, "index"), "NAS100": (1.45, 29664.0, "USD", 0.0, "index"),
}
LEVERAGE = {"fx": 30.0, "metal": 20.0, "index": 20.0}   # compte FTMO Swing (levier réduit)
COST_MULT = 2.0


def fee_pct(sym, mult=None):
    """Coût par ORDRE en % du prix = (demi-spread x mult + commission) / prix."""
    m = COST_MULT if mult is None else mult
    sp, px, ccy, comm_pct, _ = SPEC[sym]
    half = sp / 2 * m / px * 100
    comm = comm_pct if comm_pct is not None else 2.5 * _USD[ccy] / 100000 / px * 100
    return half + comm


def leverage(sym):
    return LEVERAGE[SPEC[sym][4]]


def _nth_weekday(y, m, wd, n):
    d = pd.Timestamp(y, m, 1)
    d += pd.Timedelta(days=(wd - d.weekday()) % 7)
    return d + pd.Timedelta(days=7 * (n - 1))


def us_dst(ts):
    y = ts.year
    s = _nth_weekday(y, 3, 6, 2); e = _nth_weekday(y, 11, 6, 1)
    return s <= ts.normalize() < e


FOMC = ["2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16", "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
        "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15", "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
        "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14", "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
        "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12", "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
        "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
        "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28"]


def news_times(calendar_csv=None):
    """Heures UTC des annonces à éviter. Par défaut : NFP (1er vendredi, 8:30 ET) + décision FOMC (14:00 ET) — APPROXIMATION."""
    if calendar_csv:
        return pd.to_datetime(pd.read_csv(calendar_csv)["time"], utc=True).tolist()
    out = []
    for y in range(2021, 2027):
        for m in range(1, 13):
            d = _nth_weekday(y, m, 4, 1)
            out.append((d + pd.Timedelta(hours=12, minutes=30 if us_dst(d) else 30 + 60)).tz_localize("UTC"))
    for s in FOMC:
        d = pd.Timestamp(s)
        out.append((d + pd.Timedelta(hours=18 if us_dst(d) else 19)).tz_localize("UTC"))
    return out


def flags(times, news=True, weekend=True, calendar_csv=None, before=10, after=10, wb=0):
    """(noentry, fexit) par bougie 5m : noentry = pas de remplissage/signal (ordre annulé) ; fexit = clôturer la position à la clôture de la bougie."""
    t = pd.DatetimeIndex(times).tz_convert("UTC")
    n = len(t)
    noentry = np.zeros(n, np.int8); fexit = np.zeros(n, np.int8)
    if weekend:
        mod = (t.hour * 60 + t.minute).to_numpy()
        fri = (t.weekday == 4)
        noentry |= (fri & (mod >= 19 * 60 + 30)).astype(np.int8)
        if wb > 0:   # plus de nouvelle entrée dans les wb heures qui précèdent la coupure du vendredi
            mow = (t.weekday * 1440 + t.hour * 60 + t.minute).to_numpy()
            noentry |= ((t.weekday <= 4) & (mow >= 4 * 1440 + 19 * 60 + 30 - wb * 60)).astype(np.int8)
        fexit |= (fri & (mod >= 20 * 60 + 25)).astype(np.int8)
        gap = np.r_[(t[1:] - t[:-1]).total_seconds().to_numpy() > 12 * 3600, False]   # trou de marché > 12 h : fermeture / jour férié
        fexit |= gap.astype(np.int8)
        noentry |= np.r_[False, gap[:-1]].astype(np.int8)
    if news:
        ns = t.as_unit("ns").asi8
        for T in news_times(calendar_csv):
            a = np.searchsorted(ns, (T - pd.Timedelta(minutes=before)).value); b = np.searchsorted(ns, (T + pd.Timedelta(minutes=after)).value, side="right")
            noentry[a:b] = 1
    return noentry, fexit
