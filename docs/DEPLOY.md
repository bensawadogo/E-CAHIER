# Déploiement — Ecahier

Architecture de production (2 services) :

| Couche | Techno | Hébergeur | URL publique |
|---|---|---|---|
| Frontend (Flutter Web) | build/web | **Vercel** | https://ecahier-xxxx.vercel.app |
| Backend API (FastAPI + SQLite) | Docker | **Render** | https://ecahier-api.onrender.com |

> Choix API : **Render** plutôt que Railway — plan gratuit pour une démo, disque
> persistant SQLite intégré, déploiement Docker simple (`render.yaml`).
> Inconvénient accepté : hibernation après ~15 min d'inactivité (1er accès lent).

---

## 1. Prérequis

- Comptes : [vercel.com](https://vercel.com) et [render.com](https://render.com) (gratuits).
- Node.js + **CLI Vercel** : `npm i -g vercel`
- Flutter (SDK déjà présent sur ce poste).
- Dépôt Git poussé sur GitHub.

---

## 2. Déployer l'API sur Render

Le dépôt contient `render.yaml` (infra-as-code) + `backend/Dockerfile`.

### 2-a. Rémplacer les valeurs à votre repo

Dans `render.yaml`, remplacer `repo:` par votre URL GitHub.

### 2-b. Lancer le déploiement

**Dashboard (plus simple)** :
1. allons sur [New → Blueprint](https://dashboard.render.com/blueprints/new).
2. Connecte GitHub et sélectionne ton repo.
3. Render crée le service `ecahier-api` depuis `render.yaml` et démarre le build.
4. Une fois `Live`, copie l'URL : `https://ecahier-api.onrender.com`.

2-b bis. **CLI** (alternative) : `render blueprint launch` (nécessite l'ajout du CLI Render).

### 2-c. Variables secrètes (à saisir dans le dashboard)

- `CAHIER_PII_ENCRYPTION_KEY` → génère : `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` puis copie.
- `CAHIER_AUTH_TOKEN` (optionnel) → pour activer l'auth Bearer sur /api.
  Si vous l'activez, compilez l'app avec la MÊME valeur : `--dart-define=CAHIER_AUTH_TOKEN=<valeur>` (sinon l'app reçoit 401 et garde tout en attente d'envoi).

> Notations : la base SQLite vit sur le **disque persistant** `/data/cahier_boutique.db`
> (1 Go, contenu conservé entre redémarrages et redéploiements).

### Tester l'API déployée

```
curl https://ecahier-api.onrender.com/health
# /status/commits est protégé par le jeton (si CAHIER_AUTH_TOKEN est défini) :
curl -H "Authorization: Bearer <votre jeton>" https://ecahier-api.onrender.com/status/commits
```

### 2-d. Déploiement automatique depuis la CI

Le job `deploy` de `.github/workflows/ci.yml` appelle le *Deploy Hook* de Render
après chaque push sur `main` dont les tests (Python + Flutter) passent.

1. Render → votre service → **Settings → Deploy Hook** → copier l'URL.
2. GitHub → dépôt → **Settings → Secrets and variables → Actions** → créer le
   secret `RENDER_DEPLOY_HOOK_URL` avec cette URL.

Sans ce secret, l'étape est simplement ignorée (la CI ne casse pas).

### 2-e. Nettoyer les données déjà en production (une fois)

L'ancienne app envoyait les montants en « centimes » (5 000 FCFA arrivaient
comme 500 000) et créait des doublons à chaque renvoi. **Avant** de distribuer
la nouvelle app :

```bash
# 1) Audit : lecture seule, ne modifie rien
python backend/scripts/audit_legacy_data.py --db /data/cahier_boutique.db

# 2) Corriger seulement les crédits que VOUS avez reconnus comme « ×100 »
#    (simulation par défaut)
python backend/scripts/audit_legacy_data.py --db /data/cahier_boutique.db \
    --divide-credit-by-100 ID1 ID2
# 3) puis, si la simulation est bonne :
python backend/scripts/audit_legacy_data.py --db /data/cahier_boutique.db \
    --divide-credit-by-100 ID1 ID2 --apply
```

Le script ne devine rien : un crédit de 500 000 FCFA peut être légitime. Avec
`--apply`, il fait d'abord une sauvegarde complète de la base
(`cahier_boutique.db.avant-correction-<date>`), puis corrige le crédit, le total
du client et le journal dans une seule transaction (tout ou rien). Les téléphones
reçoivent la correction à leur prochaine synchronisation. Les **doublons de
clients** sont seulement listés : à fusionner à la main.

---

## 3. Déployer le frontend sur Vercel

Vercel ne compile pas Flutter nativement ; on **pré-construit** localement puis on
envoie le dossier `build/web` (relire `.vercelignore` pour réduire).

### 3-a. Build du frontend (pointer vers l'API Render)

```bash
flutter build web --release --dart-define=CAHIER_API_BASE_URL=https://VOTRE-API.onrender.com/api
# -> génère build/web
```

> Si tu omets `--dart-define`, le client web utilisera l'origine du document
> (son propre domaine), donc il faudra que `/api` soit relayé au backend.

### 3-b. Déploiement Vercel

**Dashboard (recommandé)** :
1. Importer le repo, Framework Preset = **Other**.
2. Build Command = (vide), **Output Directory** = `build/web`.
3. Deploy. Vercel lit aussi `vercel.json` (rewrites SPA).

**CLI** :
```bash
vercel deploy build/web --prod
```

Votre URL : `https://ecahier-xxxx.vercel.app`.

---

## 4. Vérifications finales

- [ ] `https://ecahier-xxxx.vercel.app/` affiche l'app Flutter.
- [ ] `https://ecahier-api.onrender.com/health` → `{"status":"ok", ...}`
- [ ] CORS ouvert (middleware `allow_origins=["*"]`) : le frontend appelle l'API depuis un autre domaine sans souci.

---

## Table de correspondances build

| Fichier | Rôle |
|---|---|
| `backend/Dockerfile` | Image de l'API (Python 3.11 + uvicorn) |
| `backend/.dockerignore` | Exclusions de build |
| `render.yaml` | Blueprint Render (service + disque + env vars) |
| `backend/scripts/audit_legacy_data.py` | Audit / correction des données héritées (voir 2-e) |
| `vercel.json` | Config statique Vercel + rewrites SPA |
| `lib/services/api_service.dart` | Lecture de `CAHIER_API_BASE_URL` (dart-define) |