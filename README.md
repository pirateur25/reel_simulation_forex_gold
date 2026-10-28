# forex_fvg — stratégie « MSS dans un FVG HTF non mitigé »

Bot de backtest (GitHub Actions) pour EURUSD, GBPUSD, USDCHF, USDJPY, XAUUSD. Même organisation que `forex_backtest` :
historiques 5m dans `data/`, simulation prudente (SL avant TP dans la même bougie, gap = sortie à l'ouverture, frais sur chaque ordre,
1 % de risque par trade, levier max 50, un seul trade à la fois), résumé + courbe + trades sur Telegram si `BOT_TOKEN` / `CHAT_ID` existent.

## Stratégie (cas baissier ; le haussier est le miroir exact : prix inversés)
1. **Zones** : FVG baissiers (3 bougies a,b,c avec `high(c) < low(a)`) en H1 / H4 / Daily, **non mitigés** : aucune bougie CLÔTURÉE
   (H1 ou H4, réglage `mit_tf`) ouverte après la formation de la zone ne l'a touchée (`mit_depth` 0 = mèche, 1 = comblée en entier).
2. **MSS** en m5 et/ou m15 dont le sommet H2 est dans une zone : H1 = sommet confirmé (`mss_k` bougies de chaque côté), H2 > H1,
   L2 = **plus bas mèche comprise** entre H1 et H2, une bougie baissière **clôture** sous L2, et la cassure est **plus rapide que
   `speed_ratio` × la distance entre les deux sommets**. (`tests/test_mss.py` vérifie ces règles et l'absence de regard dans le futur.)
3. **Ordre** : SELL LIMIT sur le **premier FVG** de la jambe H2 → cassure (`entry_lvl` 0 = bord proche), **SL** au-dessus de H2
   (+ `sl_buf_atr` ATR), annulé si le TP est touché avant remplissage (ou après `ttl` bougies si ttl > 0).
4. **TP** : RR fixe (`tp_mode=rr`) ou prochain FVG HTF non mitigé sous l'entrée (`tp_mode=fvg`). Break-even à `be_rr` R.

## Configuration retenue (`results/best_params.json`)
15m seulement · FVG **H1** · mitigés par bougies **H4** clôturées, comblées en entier · MSS k=2, cassure ≤ 1,0 × distance entre sommets ·
SL = H2 + 2 ATR, stop minimum 0,2 % · TP fixe **RR 4**, BE à 0,7 R · longs ET shorts, filtre de tendance : clôture D1 vs EMA 50
(short sous l'EMA, long au-dessus) · ordre jamais annulé par le temps.

| Paire | Rendement | Drawdown | Trades | Espérance |
|---|---|---|---|---|
| EURUSD | +25,2 % | -10,7 % | 80 | +0,30 R |
| GBPUSD | +16,9 % | -7,6 % | 95 | +0,18 R |
| USDCHF | +10,9 % | -13,8 % | 92 | +0,12 R |
| USDJPY | +43,2 % | -11,1 % | 95 | +0,40 R |
| XAUUSD | +70,2 % | -6,8 % | 117 | +0,47 R |

(2021-01 → 2026-10, frais 0,005 %/ordre. Avec 0,01 %/ordre : +21,5 / +13,2 / +7,7 / +37,9 / +64,9 %.)
Taux de gagnants 12-21 % : normal avec RR 4 (beaucoup de sorties à zéro par le BE).

## Honnêteté sur la validation
- La configuration a été choisie sur **2021-2024** (objectif = le PIRE des deux moitiés 2021-22 / 2023-24, rendement ÷ drawdown, plafonné par paire),
  puis jugée sur **2025-2026** jamais utilisée pour choisir : EURUSD +9,9 %, GBPUSD +2,9 %, USDJPY +12,7 %, XAUUSD +26,2 %, **USDCHF −12,8 %**.
- Le filtre de tendance D1 EMA50 a été préféré à d'autres après avoir regardé les résultats toutes périodes : léger biais de sélection.
- 5m seul n'a PAS d'avantage (les stops 5m sont trop serrés, les frais mangent l'espérance) : l'entrée se fait sur le m15.
- GBPUSD et USDCHF sont les paires les plus faibles. Ce n'est pas encore au niveau de ton bot actuel et rien ne garantit le futur.

## Utilisation
- Actions → **Backtest FVG HTF + MSS** (réglages modifiables, `use_best=oui` charge `results/best_params.json`).
- Actions → **Optimisation FVG HTF + MSS** : tirage aléatoire + affinage, choix sur TRAIN, jugement sur TEST (`results_opt/`).
- En local : `pip install -r requirements.txt` puis `python backtest/run_backtest.py --best results/best_params.json`
  (le noyau C est compilé automatiquement par `gcc`).
- `results/*_trades.csv` : chaque trade avec zone HTF, H1/H2/L2 du MSS, entrée, SL, TP (utilisable dans le visualiseur de graphiques).

## Visualiser les trades sur un graphique
`viewer/viewer.html` (à ouvrir dans un navigateur, ou à régénérer avec `python backtest/export_viewer.py`) : chandeliers avec changement
d'unité de temps (5m, 15m, 30m, 1h, 4h), choix de la paire et du trade (◀ ▶), et pour chaque trade : zone FVG HTF (violet), MSS H1 / H2 / L2 (orange),
FVG d'entrée (jaune), boîtes TP (vert) et SL (rouge), niveau BE, marqueurs MSS / entrée / sortie avec le résultat en R.

## Tests sur N (bougies voisines d'un sommet) et sur la correction minimale H1 → L2
Deux réglages ont été ajoutés : `mss_k` (N : H1 doit dépasser N bougies de chaque côté ; plus N est grand, plus H1 et H2 sont éloignés)
et `min_corr_pct` / `min_corr_atr` (correction H1 → L2 minimale, sinon on prend un H1 plus ancien, `max_back` sommets en arrière au maximum).
Résultats (5 paires, config retenue, toute la période, frais 0,005 %) :

| N | rendement moyen | espérance | trades |
|---|---|---|---|
| 2 | +33,3 % | +0,30 R | 479 |
| 3 | +27,4 % | +0,22 R | 493 |
| 4 | +11,0 % | +0,10 R | 485 |
| 8 | +9,6 % | +0,12 R | 429 |
| 16 | −1,3 % | −0,02 R | 300 |

Avec N=4 / 8 / 12, tous les autres réglages ont été ré-optimisés (corrections minimales comprises) : le score d'entraînement est plus bas qu'avec
N=2 (1,61 / 1,15 / 1,57 contre 1,71) et N=8/12 ne donnent que 30-60 trades par paire. La correction minimale (0,1 à 0,5 % ou 1 à 5 ATR) réduit
le nombre de trades sans améliorer l'espérance à N=2 (0,28 R à 0,2 % contre 0,30 R sans seuil). Une descente locale depuis la config retenue
(N, correction, RR, stop minimum, marge SL, BE, vitesse) ne change rien. **Réglages conservés : N=2, pas de seuil de correction** (les deux
options restent disponibles dans le code et les workflows).

## Validation sur actifs nouveaux, coûts réels, week-end (octobre 2026)
Les deux stratégies (réglages figés, aucune ré-optimisation) ont été lancées sur 10 actifs jamais utilisés pour les régler (AUDUSD, NZDUSD, USDCAD, EURGBP,
EURJPY, GBPJPY, XAGUSD, US30, GER40, NAS100*), avec spreads/commissions FTMO x2, levier Swing. **Résultat : elles ne généralisent pas** :
FVG négative sur 9 actifs sur 10 (EURGBP +1 %), bot d'origine négatif sur 7 sur 10 (positif : EURJPY +9 %, EURGBP +3 %, NAS100 +9 % sur 1,5 an).
Seuls EURUSD, USDJPY, XAUUSD (et GBPUSD pour la FVG) restent positifs, ce qui est aussi l'ensemble sur lequel elles ont été réglées :
le chiffre « portefeuille » est donc OPTIMISTE (biais de sélection). *NAS100 = ETF CNDX (LSE, heures limitées), pas le CFD US100 de FTMO.
Week-end : sur un compte financé Standard (fermeture avant le week-end + annonces), la FVG perd l'essentiel de son avantage (+151 % -> +40 % sur 5 paires),
le bot d'origine presque pas. Challenge/Vérification FTMO et compte Swing autorisent la détention du week-end : privilégier le **Swing**.
