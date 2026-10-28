# compare/ — tests des deux stratégies avec coûts réels, week-end et annonces
- `realism.py` (dans backtest/) : spreads + commissions FTMO (x2 par prudence), levier Swing, fermeture vendredi 20:30 UTC, blocage des entrées
  autour des NFP / FOMC (calendrier APPROXIMATIF : fournir un vrai calendrier CSV colonne `time` UTC via `calendar_csv`).
- `engine_original_bot_realism.py` : moteur de ton bot original avec 2 options en plus (`noentry`, `fexit`) pour le week-end / les annonces.
  Pour l'utiliser : remplacer `backtest/engine.py` du bot original (copie de sauvegarde conseillée).
- `univ.py fvg 2.0 [we]` / `origrun.py 2.0 [we]` : lancent chaque stratégie sur les 15 actifs ; `summ.py` affiche le tableau ; `sim3.py` simule les challenges.
Chemins en dur (/tmp, /home/claude) à adapter.
