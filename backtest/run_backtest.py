# backtest/run_backtest.py — lance la stratégie FVG HTF + MSS sur une ou plusieurs paires (historiques locaux data/PAIRE.csv.gz),
# écrit les résultats dans results/ et envoie un résumé sur Telegram si BOT_TOKEN / CHAT_ID sont définis.
#
# Exemple :
#   python backtest/run_backtest.py --symbols EURUSD,USDJPY --start 2021-01-04 --params "htf=4h;rr=3;side=both"
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data  # noqa: E402
import engine  # noqa: E402
import strategy  # noqa: E402


def telegram(text=None, photo=None, document=None):
    token, chat = os.getenv("BOT_TOKEN"), os.getenv("CHAT_ID")
    if not token or not chat:
        print("TELEGRAM: BOT_TOKEN ou CHAT_ID manquant -> envoi ignoré.")
        return False
    try:
        if text:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat, "text": text[:4000]}, timeout=20)
            print("TELEGRAM sendMessage ->", r.status_code)
        if photo:
            with open(photo, "rb") as f:
                r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", data={"chat_id": chat}, files={"photo": f}, timeout=30)
            print("TELEGRAM sendPhoto ->", r.status_code)
        if document:
            with open(document, "rb") as f:
                r = requests.post(f"https://api.telegram.org/bot{token}/sendDocument", data={"chat_id": chat}, files={"document": f}, timeout=60)
            print("TELEGRAM sendDocument ->", r.status_code)
    except requests.RequestException as e:
        print("TELEGRAM erreur réseau:", e)
        return False
    return True


def summary(sym, a, st, p):
    lines = [f"📊 {sym} FVG HTF + MSS | {a.start} → {a.end or 'fin des données'}",
             f"Rendement : {st['return_pct']:+.2f} % | Max drawdown : {st['max_dd_pct']:.2f} %"]
    if st["trades"]:
        lines.append(f"Trades : {st['trades']} (long {st['longs']} / short {st['shorts']}) | gagnants {st['win_pct']:.1f} % | "
                     f"espérance {st['avg_r']:+.2f} R | profit factor {st['pf']:.2f}")
    else:
        lines.append("Aucun trade.")
    lines.append("Réglages : " + "; ".join(f"{k}={v}" for k, v in p.items()))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="EURUSD,GBPUSD,USDCHF,USDJPY,XAUUSD")
    ap.add_argument("--datadir", default="data")
    ap.add_argument("--start", default="2021-01-04")
    ap.add_argument("--end", default="")
    ap.add_argument("--capital", type=float, default=10000.0)
    ap.add_argument("--risk", type=float, default=1.0, help="risque par trade en %% du capital")
    ap.add_argument("--fee", type=float, default=0.005, help="frais par ordre en %% (0.005 = environ 1 pip aller-retour sur EURUSD)")
    ap.add_argument("--leverage", type=float, default=50.0)
    ap.add_argument("--outdir", default="results")
    ap.add_argument("--best", default="", help="fichier JSON de réglages de départ (ex: results/best_params.json)")
    ap.add_argument("--params", default="", help="réglages 'k=v;k2=v2' appliqués par-dessus")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    base = dict(strategy.PARAMS)
    if a.best:
        base.update(json.load(open(a.best)))
    p = strategy.parse_params(a.params, base)
    print("Réglages :", p)
    telegram(f"🚀 Backtest FVG HTF lancé : {a.symbols} depuis {a.start}")
    recap = []
    for sym in [s.strip().upper() for s in a.symbols.split(",") if s.strip()]:
        P = data.PairData(sym, a.datadir)
        i0 = P.idx_at(a.start)
        i1 = P.idx_at(pd.Timestamp(a.end) + pd.Timedelta(days=1)) if a.end else P.n
        sigs = strategy.signals(P, p, i0, i1)
        tr, eq, st = engine.run(P, sigs, a.capital, a.risk, a.fee, a.leverage, p["be_rr"], p["ttl"], i0, i1)
        text = summary(sym, a, st, p)
        print(text + "\n")
        tr.to_csv(os.path.join(a.outdir, f"{sym}_trades.csv"), index=False)
        open(os.path.join(a.outdir, f"{sym}_resume.txt"), "w", encoding="utf-8").write(text + "\n")
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(P.times.iloc[i0:i1].to_numpy(), eq / a.capital * 100, linewidth=1.3, label="Stratégie")
        ax.set_title(f"{sym} — {st['return_pct']:+.1f} % | DD {st['max_dd_pct']:.1f} %")
        ax.set_ylabel("Capital (base 100)")
        ax.grid(alpha=0.3)
        fig.tight_layout()
        png = os.path.join(a.outdir, f"{sym}_equity.png")
        fig.savefig(png, dpi=110)
        plt.close(fig)
        telegram(text, png)
        if len(tr):
            telegram(document=os.path.join(a.outdir, f"{sym}_trades.csv"))
        recap.append(f"{sym}: {st['return_pct']:+.1f} % | {st['trades']} trades | DD {st['max_dd_pct']:.1f} %")
    text = "📋 Récapitulatif\n" + "\n".join(recap)
    print(text)
    telegram(text)


if __name__ == "__main__":
    main()
