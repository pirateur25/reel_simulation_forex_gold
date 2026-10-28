# backtest/optimize.py — recherche de la meilleure configuration sur les 5 paires.
# Méthode : descente par coordonnées (on fait varier un réglage à la fois, on garde le meilleur, plusieurs passes).
# Pour éviter le sur-apprentissage, la configuration est choisie sur la période TRAIN (avant --split) et JUGÉE sur la période TEST
# (après --split) qu'elle n'a jamais vue. Objectif = moyenne sur les paires de (rendement / max(|drawdown|, 2 %)) : on cherche
# des gains élevés pour un drawdown faible, sur TOUTES les paires avec une seule configuration.
import argparse
import itertools
import json
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data  # noqa: E402
import engine  # noqa: E402
import strategy  # noqa: E402

SYMBOLS = ["EURUSD", "GBPUSD", "USDCHF", "USDJPY", "XAUUSD"]

# Réglages testés (valeurs possibles de chaque réglage). L'ordre = ordre de la descente.
SPACE = {
    "side": ["short", "long", "both"],
    "conf_tfs": ["5m", "15m", "5m,15m"],
    "htf": ["1h", "4h", "1d", "1h,4h", "4h,1d", "1h,4h,1d"],
    "mit_tf": ["1h", "4h"],
    "mit_depth": [0.0, 0.5, 1.0],
    "mss_k": [2, 3, 4, 6, 8, 12, 16, 24],
    "speed_ratio": [0.5, 1.0, 1.5, 2.0, 3.0, 1e9],
    "speed_ref": [0, 1],
    "trough_pivot": [0, 1],
    "min_sweep_pct": [0.0, 0.01, 0.03],
    "min_corr_pct": [0.0, 0.1, 0.2, 0.3, 0.5],
    "min_corr_atr": [0.0, 1.0, 2.0, 3.0, 5.0],
    "max_back": [3, 5, 10],
    "zone_pad_atr": [0.0, 0.5, 1.0],
    "entry_lvl": [0.0, 0.25, 0.5, 0.75, 1.0],
    "fvg_min_atr": [0.0, 0.25, 0.5],
    "sl_buf_atr": [0.0, 0.25, 0.5, 1.0, 2.0],
    "tp_mode": ["rr", "fvg"],
    "rr": [1.0, 1.5, 2.0, 2.5, 3.0, 4.0],
    "min_rr": [0.5, 1.0, 1.5, 2.0],
    "max_rr": [3.0, 5.0, 1e9],
    "tp_edge": [0.0, 0.5, 1.0],
    "be_rr": [0.0, 0.7, 1.0, 1.5, 2.0],
    "ttl": [12, 36, 96, 288, 0],
    "min_sl_pct": [0.0, 0.02, 0.05, 0.08, 0.12, 0.2],
    "trend": ["none", "4h:200", "4h:50", "1d:50", "1d:200"],
}


class Evaluator:
    def __init__(self, symbols, datadir, split, fee, risk, lev, start="2021-01-04", mid="2023-01-01"):
        self.symbols, self.fee, self.risk, self.lev = symbols, fee, risk, lev
        self.P = {}
        for s in symbols:
            t = time.time()
            self.P[s] = data.PairData(s, datadir)
            print(f"  {s}: {self.P[s].n} bougies 5m chargées ({time.time() - t:.1f}s)", flush=True)
        self.split = {s: self.P[s].idx_at(split) for s in symbols}
        self.start = {s: self.P[s].idx_at(start) for s in symbols}
        self.mid = {s: self.P[s].idx_at(mid) for s in symbols}
        self.log = []

    def run_pair(self, s, p, period):
        P = self.P[s]
        a, b = {"train": (self.start[s], self.split[s]), "h1": (self.start[s], self.mid[s]), "h2": (self.mid[s], self.split[s]),
                "test": (self.split[s], P.n), "all": (self.start[s], P.n)}[period]
        sigs = strategy.signals(P, p, a, b)
        tr, eq, st = engine.run(P, sigs, 10000.0, self.risk, self.fee, self.lev, p["be_rr"], p["ttl"], a, b)
        return tr, eq, st

    def evaluate(self, p, period="train"):
        rows = {}
        for s in self.symbols:
            _, _, st = self.run_pair(s, p, period)
            rows[s] = st
        return rows

    @staticmethod
    def half_score(rows, min_trades=8):
        """Moyenne sur les paires de (rendement / drawdown), plafonnée à ±3 par paire pour qu'une seule paire ne tire pas le score."""
        sc = [float(np.clip(st["return_pct"] / max(abs(st["max_dd_pct"]), 2.0), -3, 3)) if st["trades"] >= min_trades else -3.0
              for st in rows.values()]
        return float(np.mean(sc))

    def objective(self, p):
        """Score = le PIRE des deux moitiés de la période d'entraînement (2021-22 et 2023-24) : il faut marcher dans les deux régimes."""
        r1, r2 = self.evaluate(p, "h1"), self.evaluate(p, "h2")
        return min(self.half_score(r1), self.half_score(r2)), r1, r2

    def score(self, rows):
        return self.half_score(rows)


def fmt(rows):
    return " | ".join(f"{s}: {st['return_pct']:+.1f}% DD {st['max_dd_pct']:.1f}% {st['trades']}t" for s, st in rows.items())


def descend(ev, p, space, passes, keys=None, verbose=True):
    best = ev.objective(p)[0]
    if verbose:
        print(f"départ : score {best:.3f}", flush=True)
    for ps in range(passes):
        changed = False
        for k in (keys or list(space)):
            cur = p[k]
            cand = []
            for v in space[k]:
                q = dict(p)
                q[k] = v
                sc, r1, r2 = ev.objective(q)
                cand.append((sc, v))
                ev.log.append({"pass": ps, "param": k, "value": v, "score": sc, **{f"{s}_ret_h1": r["return_pct"] for s, r in r1.items()},
                               **{f"{s}_ret_h2": r["return_pct"] for s, r in r2.items()}})
            sc, v = max(cand, key=lambda x: x[0])
            if sc > best + 1e-9 and v != cur:
                p[k], best, changed = v, sc, True
                if verbose:
                    print(f"  pass {ps + 1}: {k} = {v}  -> score {best:.3f}", flush=True)
        if not changed:
            break
    return p, best


def random_search(ev, n, seed, keep=12):
    """Tirage aléatoire de n configurations (réglages tirés dans SPACE) ; renvoie les meilleures selon l'objectif robuste."""
    import random
    rnd = random.Random(seed)
    res = []
    t = time.time()
    for i in range(n):
        p = dict(strategy.PARAMS)
        for k, vals in SPACE.items():
            p[k] = rnd.choice(vals)
        sc, r1, r2 = ev.objective(p)
        res.append((sc, p))
        if (i + 1) % 100 == 0:
            res.sort(key=lambda x: -x[0])
            print(f"  {i + 1}/{n} configurations ({time.time() - t:.0f}s) | meilleur score {res[0][0]:.3f}", flush=True)
    res.sort(key=lambda x: -x[0])
    return res[:keep]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default=",".join(SYMBOLS))
    ap.add_argument("--datadir", default="data")
    ap.add_argument("--split", default="2025-01-01", help="début de la période TEST (jamais utilisée pour choisir)")
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--fee", type=float, default=0.005)
    ap.add_argument("--risk", type=float, default=1.0)
    ap.add_argument("--leverage", type=float, default=50.0)
    ap.add_argument("--params", default="", help="point de départ, ex 'side=short;htf=4h'")
    ap.add_argument("--only", default="", help="ne faire varier que ces réglages (séparés par des virgules)")
    ap.add_argument("--outdir", default="results")
    ap.add_argument("--random", type=int, default=0, help="nb de configurations aléatoires à tirer avant l'affinage")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--top", type=int, default=3, help="nb de meilleures configurations aléatoires à affiner")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    ev = Evaluator([s.strip().upper() for s in a.symbols.split(",")], a.datadir, a.split, a.fee, a.risk, a.leverage)
    p = strategy.parse_params(a.params)
    keys = [k.strip() for k in a.only.split(",") if k.strip()] or None
    t = time.time()
    if a.random:
        top = random_search(ev, a.random, a.seed)
        cands = []
        for sc, q in top[: a.top]:
            q, b2 = descend(ev, dict(q), SPACE, a.passes, keys, verbose=False)
            print(f"  affinage : {sc:.3f} -> {b2:.3f}", flush=True)
            cands.append((b2, q))
        best, p = max(cands, key=lambda x: x[0])
    else:
        p, best = descend(ev, p, SPACE, a.passes, keys)
    print(f"\nMeilleure configuration (score train {best:.3f}, {time.time() - t:.0f}s) :")
    print(json.dumps(p, indent=1))
    for period in ("h1", "h2", "test", "all"):
        print(f"\n[{period}] " + fmt(ev.evaluate(p, period)))
    json.dump(p, open(os.path.join(a.outdir, "best_params.json"), "w"), indent=1)
    pd.DataFrame(ev.log).to_csv(os.path.join(a.outdir, "optimisation_log.csv"), index=False)


if __name__ == "__main__":
    main()
