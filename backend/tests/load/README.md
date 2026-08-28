# Tests de charge — Ecahier (Locust)

Scénario réaliste : 1 terminal par boutique, en **offline-first**.
Trafic simulé : lectures ~80% / écritures ~20%, délai inter-tâches 0,5–4 s.

Endpoints exercés : clients, crédits, paiements, recherche, sync/status,
transactions (+ création client / crédit / paiement pour les écritures).

## Prérequis

```bash
pip install locust
```

## Lancer (interface web)

```bash
cd <racine-du-projet>
python -m locust -f backend/tests/load/locustfile.py --host http://127.0.0.1:8000
# puis ouvrir http://localhost:8089
```

## Lancer en headless (CLI, CI-ready)

```bash
python -m locust -f backend/tests/load/locustfile.py \
    --host http://127.0.0.1:8000 \
    --headless -u 50 -r 5 -t 3m \
    --csv backend/tests/load/results/load \
    --html backend/tests/load/results/report.html
```

Paramètres : `-u` utilisateurs simultanés, `-r` montée (users/s), `-t` durée.

High-level flow to follow :
1. Démarrer l'API locale (ou déployée) : `uvicorn backend.app.main:app --port 8000`
2. Lancer Locust headless (cuisine ci-dessus).
3. Lire le rapport : `backend/tests/load/results/report.html` + CSV.

## Connexion à un backend AUTH activé

Si `CAHIER_AUTH_TOKEN` est défini sur le serveur, passer le token à Locust :

```bash
# (Windows PowerShell)
$env:LOCUST_AUTH_TOKEN="votre-token"
```
Le fichier l'injecte en `Authorization: Bearer <token>` sur chaque requête.

## Convient / limites

- **Validé** : la charge réelle de l'API (FastAPI + SQLite) jusqu'à plusieurs
  dizaines/centaines de requêtes/s selon le VPS.
- Différences avec la prod : le VPS servira aussi la base de mauvaise commerce
  (photos, OCR) — il faut re-tester avec le vrai volume stocké avant une montée.

## Résultats attendus (démarrage 2 vCPU / 4 Go)

- Latence médiane lectures : quelques ms (démo)
- Le goulot ressort sur la **concurrence d'écriture SQLite** (erreurs 500/`database is locked`)
  passé un certain point — c'est la limite pratique qui justifie la migration
  PostgreSQL pour ~300+ utilisateurs.