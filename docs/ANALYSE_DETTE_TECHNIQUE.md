# 📋 RAPPORT D'ANALYSE — CODE SPAGHETTI & DETTE TECHNIQUE

**Projet :** CAHIER-BOUTIQUE  
**Date :** 31/07/2026  
**Contexte :** Application pour le Burkina Faso (connexion faible, téléphones bas/haut de gamme)

---

## 🎯 RÉSUMÉ EXÉCUTIF

| Indicateur | État | Note |
|---|---|---|
| Architecture globale | Clean Architecture / DDD intentionnelle mais incohérente | 5/10 |
| Backend (Python) | Partiellement implémenté (module Customer seul complet) | 4/10 |
| Frontend (Flutter) | **100% vide** — scaffolding de dossiers uniquement | 0/10 |
| Tests | **Aucun test** | 0/10 |
| Configuration projet | **Aucun** (pas de requirements.txt, pyproject.toml, pubspec.yaml) | 0/10 |
| Contrôle de version | **Aucun** (pas de .git, pas de .gitignore) | 0/10 |
| Sécurité | Partielle — credentials hardcoded, PII partiellement chiffré | 3/10 |
| Optimisation Burkina Faso | **Non adressée** — pas de stratégie offline-first réelle | 2/10 |

**Verdict global : 2/10** — Le projet est à un stade précoce avec une dette technique majeure.

---

## 🍝 DÉTECTION DE CODE SPAGHETTI

### 1. Couplage fort — Infrastructure ↔ Domaine

**Fichier :** `backend/app/infrastructure/database/repositories/customer_repository_impl.py`

Le repository d'infrastructure importe directement l'entité du domaine et mélange logique de chiffrement (PII) avec persistance :

```python
# Problème : la couche infrastructure contient de la logique métier (chiffrement)
# qui devrait être dans la couche application ou domaine
```

**Impact :** Violation du principe de séparation des couches. Toute modification du chiffrement casse la persistance.

### 2. Responsabilités multiples — `postgresql_connection.py`

**Fichier :** `backend/app/infrastructure/database/postgresql_connection.py`

La classe `PostgreSQLConnectionManager` gère à la fois :
- Le pool de connexions
- L'initialisation automatique (auto-connect dans `get_connection()`)
- Le logging via `print()` au lieu d'un logger

```python
# Ligne 40 : get_connection() auto-connecte si pool est None
# Couplage entre getter et initialisation — masque les erreurs de config
```

### 3. Logique métier mélangée — `customer_repository_impl.py`

Le repository implémente directement le chiffrement PII au lieu de déléguer à un service dédié. Cela crée une duplication potentielle dans chaque repository impl.

### 4. Fichiers placeholder cassés syntaxiquement

**Fichiers concernés :**
- `backend/app/domain/entities/payment.py` — placeholder invalide
- `backend/app/domain/entities/transaction.py` — placeholder invalide
- `backend/app/domain/entities/credit.py` — **VIDE** (0 octet)

**Impact :** Imports impossibles, application non démarrable.

--- 

## 💰 INVENTAIRE DE LA DETTE TECHNIQUE

### 🔴 Critique (P0)

| # | Dette technique | Fichier(s) | Impact |
|---|---|---|---|
| 1 | **Frontend 100% vide** | `frontend/lib/**` | Aucune UI, aucune app livrable |
| 2 | **Aucun contrôle de version** | Racine projet | Historique perdu, rollback impossible |
| 3 | **Aucun fichier de config backend** | `backend/` | Pas de requirements.txt, pyproject.toml — dépendances non gérées |
| 4 | **Aucun fichier de config frontend** | `frontend/` | Pas de pubspec.yaml — projet Flutter non initialisé |
| 5 | **Credentials hardcoded** | `postgresql_connection.py:13` | Faille de sécurité — credentials DB en clair |
| 6 | **Entités domaine cassées** | `credit.py`, `payment.py`, `transaction.py` | App non fonctionnelle |
| 7 | **Aucun test** | `backend/tests/` (vide) | Aucune garantie de qualité, régressions invisibles |

### 🟠 Élevée (P1)

| # | Dette technique | Fichier(s) | Impact |
|---|---|---|---|
| 8 | **Scripts temporaires à la racine** | `_b1.py`, `_build_files.py`, `_gen_all.py`, `_gen2.py`, `_generate.py`, `_gen_ocr.py`, `_write_all.py`, `_write_helper.py`, `_write_ocr.py`, `build_all.py`, `gen_all.py`, `create_files.ps1` | 12 fichiers de code mort polluant le projet |
| 9 | **Fichiers suspects** | `sqlite3.Connection`, `-p` | Fichiers créés par erreur, confusion |
| 10 | **Artefacts de test** | `_ocr_b64.txt`, `_test.txt`, `backend/app/application/dto/test_write.txt` | Données potentiellement sensibles, pollution |
| 11 | **`print()` au lieu de logging** | `postgresql_connection.py:25,32` | Pas de logs structurés, debug difficile |
| 12 | **`__pycache__` non ignorés** | `backend/app/domain/entities/__pycache__/`, etc. | Fichiers compilés dans le projet |
| 13 | **Sync simulée/incomplète** | `sync_queue.py`, `sync_service.py` | Pas de vraie stratégie offline-first |
| 14 | **OCR placeholder** | `ocr_engine.py` | Fonctionnalité OCR non implémentée |
| 15 | **Couche présentation vide** | `backend/app/presentation/api/`, `middleware/` | Aucun endpoint API |
| 16 | **Couche application vide** | `backend/app/application/services/`, `dto/` | Aucun use case orchestré |
| 17 | **Couche use_cases vide** | `backend/app/domain/use_cases/` | Aucune logique métier |

### 🟡 Moyenne (P2)

| # | Dette technique | Fichier(s) | Impact |
|---|---|---|---|
| 18 | **Types manquants** | Tous fichiers Python | Pas de type hints, erreurs runtime possibles |
| 19 | **Absence de gestion d'erreurs** | `postgresql_connection.py` | Pas de retry, pas de fallback |
| 20 | **Sécurité PII partielle** | `pii_encryptor.py` | Chiffrement présent mais non appliqué uniformément |
| 21 | **Duplication potentielle** | Repositories impl | Chaque impl devra répéter le pattern de chiffrement |
| 22 | **Pas de documentation** | `docs/` (vide) | Aucun README, aucun guide |
| 23 | **Pas de .env.example** | Racine | Configuration non documentée |

---

## 🌍 ÉVALUATION CONTEXTE BURKINA FASO

### Connectivité faible — ❌ Non adressée

| Exigence | État | Détail |
|---|---|---|
| Stratégie offline-first | ❌ Absente | `sync_queue.py` et `sync_service.py` sont simulés |
| Cache local (SQLite) | ⚠️ Partiel | `sqlite_connection.py` existe mais non intégré au sync |
| Synchronisation différée | ❌ Absente | Pas de queue de sync réelle |
| Reprise sur échec réseau | ❌ Absente | Pas de retry, pas de backoff |
| Compression des données | ❌ Absente | Pas de compression des payloads |
| Requêtes optimisées | ❌ Absente | Pas de pagination, pas de champs sélectionnés |

### Téléphones bas de gamme — ❌ Non adressée

| Exigence | État | Détail |
|---|---|---|
| Frontend léger | ❌ N/A | Frontend vide |
| Lazy loading | ❌ N/A | Frontend vide |
| Images optimisées | ❌ N/A | Frontend vide |
| Mémoire limitée | ❌ N/A | Frontend vide |
| Taille APK réduite | ❌ N/A | Pas de pubspec.yaml |

### Téléphones haut de gamme — ❌ Non adressée

| Exigence | État | Détail |
|---|---|---|
| Fonctionnalités avancées (caméra, OCR, voix) | ❌ Absent | Modules `ocr_engine.py`, `features/camera/`, `features/voice/` vides |
| Performance GPU | ❌ N/A | Frontend vide |

---

## 📊 ÉTAT D'IMPLÉMENTATION PAR MODULE

### Backend

| Module | Entité | Repository (domaine) | Repository (infra) | Use Case | DTO | API |
|---|---|---|---|---|---|---|
| Customer | ✅ Implémenté | ✅ Implémenté | ✅ Implémenté | ❌ Vide | ❌ Vide | ❌ Vide |
| Credit | ❌ Vide | ❌ Placeholder | ❌ Placeholder | ❌ Vide | ❌ Vide | ❌ Vide |
| Payment | ❌ Placeholder cassé | ❌ Placeholder | ❌ Placeholder | ❌ Vide | ❌ Vide | ❌ Vide |
| Transaction | ❌ Placeholder cassé | ❌ Placeholder | ❌ Placeholder | ❌ Vide | ❌ Vide | ❌ Vide |

### Frontend

| Module | État |
|---|---|
| `lib/core/` | ❌ Vide |
| `lib/data/datasources/` | ❌ Vide |
| `lib/data/repositories/` | ❌ Vide |
| `lib/domain/entities/` | ❌ Vide |
| `lib/domain/repositories/` | ❌ Vide |
| `lib/domain/use_cases/` | ❌ Vide |
| `lib/features/camera/` | ❌ Vide |
| `lib/features/credits/` | ❌ Vide |
| `lib/features/customers/` | ❌ Vide |
| `lib/features/ocr/` | ❌ Vide |
| `lib/features/search/` | ❌ Vide |
| `lib/features/settings/` | ❌ Vide |
| `lib/features/sync/` | ❌ Vide |
| `lib/features/voice/` | ❌ Vide |
| `lib/features/widgets/` | ❌ Vide |
| `lib/presentation/providers/` | ❌ Vide |
| `lib/presentation/screens/` | ❌ Vide |
| `lib/shared/` | ❌ Vide |

---

## ✅ RECOMMANDATIONS PRIORISÉES

### Phase 1 — Fondations (Critique)

1. **Initialiser Git** — `git init`, créer `.gitignore` (Python, Flutter, IDE)
2. **Supprimer les 12 scripts temporaires** — `_b1.py`, `_build_files.py`, `_gen_all.py`, `_gen2.py`, `_generate.py`, `_gen_ocr.py`, `_write_all.py`, `_write_helper.py`, `_write_ocr.py`, `build_all.py`, `gen_all.py`, `create_files.ps1`
3. **Supprimer les fichiers suspects** — `sqlite3.Connection`, `-p`, `_ocr_b64.txt`, `_test.txt`, `backend/app/application/dto/test_write.txt`
4. **Nettoyer les `__pycache__`** — ajouter au `.gitignore`
5. **Créer `backend/requirements.txt`** ou `pyproject.toml` — figer les dépendances (fastapi, asyncpg, sqlite3, pydantic, cryptography)
6. **Initialiser le projet Flutter** — `flutter create .` dans `frontend/`, créer `pubspec.yaml`
7. **Externaliser les credentials** — créer `.env`, `.env.example`, utiliser `python-dotenv`
8. **Corriger les entités cassées** — implémenter `credit.py`, `payment.py`, `transaction.py`

### Phase 2 — Architecture & Sécurité (Élevée)

9. **Implémenter la couche présentation** — créer les routers FastAPI, middleware
10. **Implémenter la couche application** — services, DTOs, use cases
11. **Centraliser le chiffrement PII** — service dédié injecté dans les repositories
12. **Remplacer `print()` par `logging`** — configurer un logger structuré
13. **Implémenter une vraie stratégie offline-first** :
    - SQLite local comme source de vérité
    - Queue de synchronisation persistante
    - Retry avec backoff exponentiel
    - Détection de connectivité
14. **Ajouter les type hints** sur tout le code Python
15. **Implémenter l'OCR** — `ocr_engine.py` (Tesseract ou API cloud avec fallback offline)

### Phase 3 — Tests & Qualité (Élevée)

16. **Écrire des tests unitaires** — pytest pour le domaine, les repositories, la sécurité
17. **Écrire des tests d'intégration** — API endpoints, sync
18. **Ajouter un linter** — `ruff` ou `flake8` pour Python, `flutter_lints` pour Dart
19. **Ajouter un formateur** — `black` pour Python, `dart format`
20. **CI/CD** — GitHub Actions ou similaire

### Phase 4 — Optimisation Burkina Faso (Moyenne)

21. **Compression des payloads API** — gzip, champs sélectionnés
22. **Pagination** — tous les endpoints de liste
23. **Cache HTTP** — ETag, Cache-Control
24. **Frontend léger** — éviter les dépendances lourdes, préférer Material 3
25. **Images optimisées** — WebP, resize, cache
26. **Lazy loading** — chargement différé des écrans
27. **Taille APK** — `--split-per-abi`, ProGuard/R8
28. **Mode hors-ligne** — tout fonctionne sans connexion, sync au retour réseau

### Phase 5 — Documentation (Moyenne)

29. **README.md** — installation, démarrage, architecture
30. **ARCHITECTURE.md** — diagramme, décisions techniques
30. **API.md** — documentation des endpoints (OpenAPI/Swagger)
31. **DEPLOYMENT.md** — guide de déploiement

---

## 📈 MÉTRIQUES DE DETTE TECHNIQUE

| Métrique | Valeur |
|---|---|
| Fichiers de code mort | 12 scripts + 4 suspects = 16 |
| Fichiers vides (backend) | 7 sur 18 (39%) |
| Fichiers vides (frontend) | 24 sur 24 (100%) |
| Tests | 0 |
| Coverage | 0% |
| TODOs/FIXMEs | À évaluer |
| Lignes de code (backend) | ~500 (estimation) |
| Lignes de code (frontend) | 0 |
| Modules implémentés | 1/4 (Customer) |
| Endpoints API | 0 |
| Dette technique estimée | **~80% du projet** |

---

## 🎯 CONCLUSION

Le projet CAHIER-BOUTIQUE présente une **dette technique critique** :

1. **Le frontend est inexistant** — 24 dossiers vides, pas même un `pubspec.yaml`
2. **Le backend est partiellement implémenté** — seul le module Customer fonctionne
3. **Aucune stratégie offline-first** — critique pour le contexte Burkina Faso
4. **16 fichiers de code mort** polluent la racine
5. **Aucun contrôle de version** — risque de perte totale
6. **Sécurité insuffisante** — credentials hardcoded, PII partiellement protégée
7. **Aucun test** — qualité non garantie

**Recommandation immédiate :** Nettoyer le projet (Phase 1) avant toute nouvelle fonctionnalité. La fondation actuelle ne supportera pas le poids d'un développement ultérieur sans refactorisation majeure.

---

*Rapport généré par analyse automatisée — 31/07/2026*