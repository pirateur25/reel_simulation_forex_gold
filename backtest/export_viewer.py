# backtest/export_viewer.py — génère viewer/viewer.html : graphique en chandeliers interactif (TradingView lightweight-charts)
# avec, pour chaque trade : zone FVG HTF, MSS (H1, H2, L2), FVG d'entrée, boîtes TP/SL, BE, changement d'unité de temps.
#   python backtest/export_viewer.py --best results/best_params.json --out viewer/viewer.html
import argparse, base64, gzip, json, os, sys
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data, engine, strategy  # noqa: E402

ep = lambda s: int(pd.Timestamp(s).timestamp())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="EURUSD,GBPUSD,USDCHF,USDJPY,XAUUSD")
    ap.add_argument("--datadir", default="data")
    ap.add_argument("--best", default="results/best_params.json")
    ap.add_argument("--params", default="")
    ap.add_argument("--fee", type=float, default=0.005)
    ap.add_argument("--out", default="viewer/viewer.html")
    ap.add_argument("--pad_days", type=float, default=32.0, help="jours de bougies 5m gardés avant/après chaque trade (le visualiseur affiche jusqu'à 30 j de contexte avant le signal)")
    a = ap.parse_args()
    base = dict(strategy.PARAMS)
    base.update(json.load(open(a.best)))
    p = strategy.parse_params(a.params, base)
    out = []
    for sym in [s.strip().upper() for s in a.symbols.split(",") if s.strip()]:
        P = data.PairData(sym, a.datadir)
        tr, eq, st = engine.run(P, strategy.signals(P, p), 10000.0, 1.0, a.fee, 50.0, p["be_rr"], p["ttl"])
        print(sym, st["trades"], "trades")
        div = 1000 if P.base["c"][0] > 50 else 100000
        T = []
        for r in tr.itertuples():
            T.append(dict(side=r.side, te=ep(r.entry_time), tx=ep(r.exit_time), ts=ep(r.signal_time), entry=r.entry, exit=r.exit, sl=r.sl, tp=r.tp,
                          reason=r.reason, r=float(r.r), pnl=float(r.pnl), tf=r.conf_tf, h1p=r.mss_h1, h1t=ep(r.h1_time), h2p=r.mss_h2, h2t=ep(r.h2_time),
                          l2p=r.mss_l2, l2t=ep(r.l2_time), zlo=r.zone_lo, zhi=r.zone_hi, zt=ep(r.zone_form), fl=r.fvg_lo, fh=r.fvg_hi,
                          ft1=ep(r.fvg_t1), be=p["be_rr"]))
        pad = int(a.pad_days * 86400)
        iv = sorted((min(x["h1t"], x["ft1"], x["ts"]) - pad, x["tx"] + pad) for x in T)
        m = []
        for s0, s1 in iv:
            if m and s0 <= m[-1][1]: m[-1][1] = max(m[-1][1], s1)
            else: m.append([s0, s1])
        ts_ = (P.base["open_ns"] // 10**9).astype(np.int64)
        O, H, L, C = (np.rint(P.base[k] * div).astype(np.int64) for k in "ohlc")
        segs = []
        for s0, s1 in m:
            idx = np.flatnonzero((ts_ >= s0) & (ts_ <= s1))
            if not len(idx): continue
            v, pt, pc = [int(ts_[idx[0]] // 300), int(O[idx[0]])], ts_[idx[0]] // 300, O[idx[0]]
            for i in idx:
                tt = ts_[i] // 300
                v += [int(tt - pt), int(O[i] - pc), int(H[i] - O[i]), int(O[i] - L[i]), int(C[i] - O[i])]
                pt, pc = tt, C[i]
            segs.append(v)
        b64 = base64.b64encode(gzip.compress(json.dumps(segs, separators=(",", ":")).encode(), 9)).decode()
        out.append({"name": sym, "div": div, "trades": T, "b64": b64})
    html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "viewer", "template.html"), encoding="utf-8").read()
    html = html.replace("/*DATA*/", json.dumps(out, separators=(",", ":")))
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(html)
    print(f"{a.out} : {len(html) / 1e6:.1f} Mo")


if __name__ == "__main__":
    main()
