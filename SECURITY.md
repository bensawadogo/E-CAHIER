# Politique de securite - Ecahier / CAHIER-BOUTIQUE

Application offline-first pour boutiques au Burkina Faso (connexion faible,
materiel modeste). Ce document decrit les garde-fous en place et les
procedures en cas d incident.

## Garde-fous anti-fuite de secrets

| Couche | Mecanisme |
|---|---|
| .gitignore | .env, .pii_key*, *.key, *.pem, *.jks, *.keystore, *.db*, data/, graphify/ |
| Pre-commit | scripts/hooks/pre-commit (active via core.hooksPath) -> scanner avant chaque commit |
| CI | Job secret-scan (.github/workflows/ci.yml) -> python scripts/check_secrets.py avant les tests |
| Scanner | scripts/check_secrets.py : motifs secrets + fichiers interdits dans l index git |

Reactiver le hook local apres un clone :

    git config core.hooksPath scripts/hooks

Exception justifiee : git commit --no-verify (a eviter, traçable).

## Secrets et leur cycle de vie

| Secret | Source | Rotation |
|---|---|---|
| CAHIER_PII_ENCRYPTION_KEY | .env (jamais versionne) | MultiFernet + scripts/rotate_pii_key.py ; ancienne cle gardee en fichier legacy le temps de la migration |
| CAHIER_AUTH_TOKEN | .env (vide = auth off, dev uniquement) | A chaque compromission ; prevoir longueur >= 32 caracteres |
| DATABASE_URL | .env / secrets CI (GitHub Actions) | Via portail Azure |

Rappel : deux cles PII reelles coexistaient (.env vs backend/.pii_key_main).
La cle faisant foi est celle de CAHIER_PII_ENCRYPTION_KEY. Ne jamais commiter
le fichier .pii_key_main.

## Regles d or

1. Aucun credential dans le code source, les tests ou les logs.
2. Les tests utilisent exclusivement des jetons fictifs et des cles generees.
3. Pas de donnees client reelles dans les fixtures ou la documentation.
4. En production : CAHIER_DEBUG=false (l endpoint /_echo renvoie 404 hors debug).

## En cas de fuite suspectee

1. Revoquer / rotater immediatement le secret concerne (voir table ci-dessus).
2. Si un commit contient un secret : purger l historique (git filter-repo)
   puis forcer push — un simple revert ne retire PAS le secret de l historique.
3. Verifier les logs applicatifs pour une exposition eventuelle.
4. Consigner l incident dans docs/ (date, perimetre, action corrective).

## Points connus restants (audit 25/08/2026)

- Hash mot de passe SHA256+salt fait maison dans infrastructure/auth :
  migrer vers argon2/bcrypt.
- Android release signe avec la cle debug (android/app/build.gradle.kts:37) :
  configurer un keystore de release avant publication.
- Actions GitHub pincees par tag et non par SHA.
- Purger les commits dangling avant toute publication publique (git gc --prune=now).
- Supprimer data/cahier_boutique.db.pre_rotation (copie DB clients inutile).
- Base URL API hardcodee (http://10.0.2.2:8000) dans lib/services/api_service.dart :
  externaliser via --dart-define avant deploiement.
