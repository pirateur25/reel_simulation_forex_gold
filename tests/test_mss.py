# tests/test_mss.py — vérifie la définition du MSS (python tests/test_mss.py).
#  1) L2 (le niveau cassé) est bien le point le PLUS BAS (mèche comprise) entre les 2 sommets ;
#  2) H1 est un vrai sommet (k bougies de chaque côté), H2 > H1, la cassure clôture sous L2 avec une bougie baissière ;
#  3) la cassure est plus rapide que ratio x la distance entre les 2 sommets ;
#  4) aucun regard dans le futur : couper les données ne change pas les signaux passés.
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backtest"))
import native


def series(n, seed):
    r = np.random.default_rng(seed)
    c = 100 + np.cumsum(r.normal(0, 0.3, n))
    o = np.concatenate([[c[0]], c[:-1]])
    h = np.maximum(o, c) + np.abs(r.normal(0, 0.15, n))
    l = np.minimum(o, c) - np.abs(r.normal(0, 0.15, n))
    return o, h, l, c


def check(seed, k, ratio, spmode, cp=0.0, ca=0.0):
    o, h, l, c = series(4000, seed)
    atr = np.full(len(h), 0.5)
    ev = native.mss_events(h, l, c, o, k, ratio, spmode, 0, 0.0, atr, cp, ca, 6)
    for t, h1i, h2i, li, h1p, h2p, l2p in zip(ev["t"], ev["h1i"], ev["h2i"], ev["li"], ev["h1p"], ev["h2p"], ev["l2p"]):
        seg = l[h1i + 1: h2i + 1]
        assert l2p == seg.min() and l[li] == l2p, "L2 n'est pas le plus bas (mèche comprise) entre les 2 sommets"
        assert h2p > h1p and h[h1i] == h1p and h[h2i] == h2p
        assert (h1p - l2p) >= max(cp / 100 * h1p, ca * 0.5) - 1e-12, "correction H1 -> L2 trop petite"
        assert h1p >= h[max(0, h1i - k): h1i + k + 1].max() - 1e-12 and h1p > h[h1i - k: h1i].max()
        assert h[h1i] > h[h1i - k: h1i].max() and h[h1i] >= h[h1i + 1: h1i + k + 1].max(), "H1 n'est pas un sommet confirmé"
        assert h2p == h[h1i + 1: t + 1].max() or h2p == h[h2i], "H2 n'est pas le plus haut depuis H1"
        assert c[t] < l2p and c[t] < o[t] and t > h2i
        ref = (h2i - h1i) if spmode == 0 else (h2i - li)
        assert (t - h2i) <= ratio * ref, "cassure trop lente"
    # causalité : on coupe les données à m, les événements avant m-1 doivent être identiques
    m = 2500
    ev2 = native.mss_events(h[:m], l[:m], c[:m], o[:m], k, ratio, spmode, 0, 0.0, atr[:m], cp, ca, 6)
    a, b = ev["t"][ev["t"] < m], ev2["t"]
    assert np.array_equal(a, b), "regard dans le futur détecté"
    return len(ev["t"])


if __name__ == "__main__":
    tot = 0
    for seed in range(5):
        for k in (2, 3, 5):
            for ratio in (1.0, 2.0, 1e9):
                for sp in (0, 1):
                    tot += check(seed, k, ratio, sp)
                    tot += check(seed, k, ratio, sp, 0.5, 0.0) + check(seed, k, ratio, sp, 0.0, 2.0)
    print(f"OK : {tot} MSS vérifiés (L2 = vrai plus bas mèche comprise, cassure rapide, pas de regard dans le futur)")
