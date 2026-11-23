# Dette technique — état actuel

Remplace l'ancien rapport (juillet 2026), devenu faux : il décrivait un projet
sans Flutter, sans tests et sans git.

**Contexte :** boutiquiers au Burkina Faso, téléphones modestes, connexion
faible et intermittente. Toute décision se juge à : *écrire d'abord sur le
téléphone, ne jamais bloquer sur le réseau, ne jamais perdre une donnée sans le dire.*

## Corrigé

### Application Flutter

| Sujet | Avant | Maintenant |
|---|---|---|
| Compilation | ne compilait pas (erreurs de syntaxe, `lucide_icons` incompatible Flutter 3.47, `CardTheme`) | compile ; `flutter analyze` propre |
| Lecture | API d'abord, jusqu'à ~42 s d'attente avant de lire la base locale | toujours locale, instantanée |
| Écriture | attendait l'API (jusqu'à ~42 s) | transaction SQLite locale puis envoi en arrière-plan |
| Téléchargement | relisait TOUTE la base à chaque synchro | **incrémental** : `?updated_since=` + curseur par ressource (table `sync_meta`, base v3), écrit dans la même transaction que les données |
| Contrat app ↔ API | l'app attendait une liste, l'API renvoie `{customers:[…], total}` ; montants en chaînes ; pas de `credit_id` ; statuts différents | alignés, testés contre le vrai backend (`test/e2e_backend_test.dart`) |
| Doublons | le serveur ignorait l'id de l'app ; renvoi = doublon | création idempotente par id (UUID généré sur le téléphone) |
| Perte silencieuse | tout code HTTP « réussi » marquait l'envoi comme fait (422/401 inclus) | seuls les 2xx ; refus = « Non envoyé » visible + bouton Réessayer ; 401 = arrêt |
| Montants | saisie ×100 (« centimes ») ; le FCFA n'en a pas : 5 000 devenait 500 000 | FCFA entiers ; migration locale v1 → v2 → v3 |
| Jeton d'API | l'app n'envoyait aucun `Authorization` | `--dart-define=CAHIER_AUTH_TOKEN=…` |
| Double appui sur « Enregistrer » | doublons | bouton désactivé pendant l'enregistrement |
| Paiement sans crédit | impossible (422) | choix client → crédit ; montant ≤ reste à payer ; crédit mis à jour |
| Onglets | rechargement complet à chaque changement | construits à la demande puis conservés |
| Dépendances | 2 jeux d'icônes + `intl` + `shared_preferences` + `cupertino_icons` | icônes Material intégrées, 0 paquet superflu |
| Code dupliqué | 5 `EcahierRepository`, `FutureBuilder` ×15, DAO ×3 | repository unique, `RepoBuilder`, `BaseDao`, `RecordTile` |
| Texte agrandi / petit écran | grille à proportion fixe, `ListTile` serrés, lignes sans retour à la ligne : débordements | corrigés et **testés** (onglets à 100/150/200 %, formulaires de saisie à 100/200 %) sur 360×640 avec la police Roboto réelle |

### API (backend)

| Sujet | Avant | Maintenant |
|---|---|---|
| Atomicité | `main.py` ne passait pas `connection_manager` : crédit/paiement + total client + journal en commits séparés | une seule transaction (tout ou rien), testée avec un échec simulé |
| Concurrence | 20 paiements simultanés → ~10 erreurs et total client faux (300 au lieu de 2 000) ; 30 requêtes simultanées → `InterfaceError` | verrou autour de la connexion partagée et de `transaction()` (RLock), connexion de transaction réutilisée ; tests de charge en threads |
| Injection des services | variables globales `set_*_service` | `Depends` + `app.state` (aucun état global de module) |
| `/status/commits` | public, expose l'historique git | derrière le jeton Bearer (le proxy du tableau de bord web l'ajoute déjà) ; `limit` borné 1–50 |
| Lecture incrémentale | absente | `?updated_since=` sur clients, crédits, paiements (index sur `updated_at`, tri stable, borne inclusive) |
| Paiement sur le crédit d'un autre client | accepté | refusé (400) |
| Modifier / supprimer un crédit ou un paiement (`PUT`/`DELETE`) | ne recalculait ni le total du client ni le statut du crédit | recalcul systématique (règles dans `services/ledger.py`), en une transaction ; un crédit annulé ne compte plus dans la dette |
| Supprimer un crédit qui a des paiements | erreur 500 (clé étrangère) | refus propre **409** « annulez-le plutôt » |
| `updated_at` sur les modifications | jamais mis à jour par un `PUT` : la lecture incrémentale aurait ignoré la modification | mis à jour à chaque `update()` de client, crédit et paiement |
| Code mort dangereux | `AuthManager.verify_token` acceptait n'importe quel `x:y` | supprimé |
| Doublons de code | `CustomerResponse(...)` ×5 | `_to_response` |

### Projet

| Sujet | Avant | Maintenant |
|---|---|---|
| CI | ne testait que Python (3.14, alors que l'image Docker est en 3.11) | Python **3.11** (= production) + `flutter analyze` + `flutter test` |
| Déploiement CI | job Azure alors que le projet est sur Render | appel du *Deploy Hook* Render (secret `RENDER_DEPLOY_HOOK_URL`, ignoré s'il est absent) |
| Données héritées | rien | `backend/scripts/audit_legacy_data.py` (audit en lecture seule + correction sauvegardée) |

## Reste à faire (par priorité)

1. **Jeton partagé dans l'app.** `CAHIER_AUTH_TOKEN` est le même pour tous les
   appareils et se lit dans l'APK. Remplacer par une authentification par
   boutique/utilisateur avant d'ouvrir à plusieurs commerçants.
2. **Nettoyer les données déjà en production** avec
   `backend/scripts/audit_legacy_data.py` (voir `docs/DEPLOY.md`). Le script
   liste, il ne devine pas : c'est vous qui désignez les crédits « ×100 ».
3. **Modifications et suppressions hors ligne.** Seules les créations sont
   synchronisées : il faudra une règle de conflit entre téléphones (dernier
   écrit gagne ? par champ ?). Le serveur, lui, gère maintenant correctement
   les modifications et suppressions (voir plus haut).
4. **Un paiement supérieur au reste à payer est accepté par le serveur** (le
   crédit passe « payé »). C'est un comportement voulu et testé
   (`test_overpayment_marks_credit_paid`), l'app l'interdit côté saisie. À
   revoir seulement si vous voulez gérer les avances.
5. **Test sur vrai téléphone bas de gamme / réseau 2G bridé** (émulateur
   Android + limitation réseau) : non fait. Le test de texte agrandi
   couvre les onglets et les formulaires, mais pas un clavier ouvert (la
   saisie réelle).
6. **Contraste en plein soleil** : à vérifier sur appareil réel (le texte ambre
   a été foncé, rien de plus n'est mesuré).
7. **Les enregistrements supprimés côté serveur** ne disparaissent pas des
   téléphones (la lecture incrémentale ne transporte pas les suppressions).
8. **Données locales de l'ancienne app (v1).** À la mise à jour, les éléments
   jamais envoyés passent en « Non envoyés (ancien format) ». Si l'ancienne
   version avait déjà envoyé des éléments, ils existent côté serveur sous un
   autre identifiant : un doublon peut apparaître. L'ancienne version ne
   compilait pas, donc peu d'appareils sont concernés.

## Lancer les tests

```
python -m pytest backend/tests            # backend : 496 tests
flutter test                              # app : 113 tests (+ 4 de bout en bout ignorés sans serveur)
# bout en bout contre un vrai serveur :
CAHIER_AUTH_TOKEN=e2e-token python -m uvicorn backend.app.main:app --port 8765
E2E_API=http://127.0.0.1:8765/api flutter test test/e2e_backend_test.dart
```

### Où est quoi

| Type | Backend | Flutter |
|---|---|---|
| **Unitaires avec mocks** (aucune base, aucun réseau) | `test_unit_services_mocked.py` (services et règles de solde, dépôts simulés), `test_unit_api_mocked_services.py` (routes HTTP, services simulés), `test_unit_middleware_and_params.py` | `api_service_test.dart` (client HTTP simulé, `mocktail`), `repository_mocked_api_test.dart` (API simulée), `sync_screen_test.dart` (repository simulé) |
| **Intégration** (vraie base SQLite) | `test_integration_scenarios.py` (téléphones, curseurs, suite d'opérations aléatoires qui vérifie les soldes), `test_ledger_integrity.py`, `test_transactions_atomicity.py`, `test_updated_since.py`, `integration/` | `dao_test.dart`, `repository_sync_test.dart`, `widget_test.dart` (texte agrandi) |
| **Bout en bout** (app contre vrai serveur) | — | `e2e_backend_test.dart` (opt-in via `E2E_API`) |
