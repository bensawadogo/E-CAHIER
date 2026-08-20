# 🧪 RAPPORT DE TEST — FRONTEND CAHIER BOUTIQUE

**URL testée :** http://localhost:8000/
**Date :** 09/08/2026
**Méthode :** ouverture dans Chrome headless (chargement OK, HTTP 200) + analyse du DOM servi + exécution des fonctions JS dans Node (DOM simulé).

---

## 1. ✅ CE QUI FONCTIONNE

| Élément | Comportement constaté |
|---|---|
| Chargement de la page | OK — serveur statique actif sur le port 8000, page rendue |
| Navigation entre vues | ✅ `switchView('home'/'clients'/'credits'/'sync')` fonctionne (testé : la classe `active` bascule correctement sur la bonne section, menu desktop + bottom bar mobile) |
| Partage WhatsApp | ✅ `shareWhatsApp(...)` ouvre `https://wa.me/<tel>?text=...` (testé en Node, URL bien formée et encodée) |
| 4 vues présentes | `#view-home`, `#view-clients`, `#view-credits`, `#view-sync` |

## 2. ⚠️ BOUTONS PRÉSENTS MAIS INERTES (AUCUNE ACTION)

### `index.html`

| Bouton | Emplacement | Problème |
|---|---|---|
| Menu hamburger (mobile) | Header | Aucun `onclick` — ne fait rien (ni drawer mobile) |
| Appeler (×2) | Alertes échéances | Aucun `onclick` — devrait ouvrir `tel:` |
| **Tous / En attente / En retard** | Filtres crédits | Aucun `onclick` — filtrage inopérant |
| **Enregistrer Paiement** | Fiche crédit | Aucun `onclick` — ne fait rien |
| **Lancer la synchronisation** | Vue Sync | Aucun `onclick` — ne fait rien |
| Champ « Chercher un client... » | Vue Clients | Pas de `oninput`/`onkeyup` — recherche inerte |

### `clients-retard.html` et `clients-retard-new.html` (100 % des boutons inertes)

| Bouton | Problème |
|---|---|
| Retour `arrow_back` | Aucun `onclick` — ne retourne nulle part |
| Tous / Plus de 50.000 F / Moins de 50.000 F | Filtres montant sans action |
| Tous retards / Plus de 30 jours / Moins de 30 jours / Retards critiques | Filtres retard sans action |
| Appeler (×4) | Aucun `tel:` |
| WhatsApp (×4) | Aucun `onclick` — n'ouvre rien (contrairement à index.html) |
| **WhatsApp Groupé** | Aucun `onclick` |

## 3. BOUTONS / FONCTIONS MANQUANTS

### Clients
- "Ajouter un client" : le bouton "Nouveau Client" navigue vers la liste mais n'ouvre aucun formulaire
- Modifier un client : aucun bouton ni formulaire d'edition
- Desactiver / reactiver un client (is_active) : absent
- Supprimer un client : absent
- Recherche active : champ present mais aucune logique de filtrage
- Details client : le bouton "Details" appelle shareWhatsApp au lieu d'afficher la fiche client

### Crédits
- "Ajouter un crédit" : aucun formulaire (choix client, montant FCFA, description, échéance 30 j)
- Modifier un crédit : absent
- Supprimer un crédit : absent
- Filtres fonctionnels (pending_only / overdue_only) : boutons présents mais inertes
- Affichage des statuts complets : seul "Retard" est affiché ; pas de "en attente / partiel / payé / annulé"

### Paiements
- Page / vue Paiements dédiée : absente de la navigation
- "Enregistrer un paiement" : le bouton existant est inerte ; aucun formulaire (client, crédit, montant, méthode Espèces/Mobile Money/Virement/Autre, référence)
- Liste des paiements : absente
- Mise à jour auto du statut du crédit après paiement : existe côté backend mais pas branchée

### Synchronisation
- Bouton "Lancer la synchronisation" : inerte (devrait appeler POST /api/sync/push)
- Indicateur d'opérations en attente : absent (backend : GET /api/sync/pending)
- Message "Connecté / Pas de connexion" : absent
- "Dernière synchro : Aujourd'hui, 08:30" : valeur codée en dur

### Global
- AUCUNE intégration API : 0 fetch, 0 XMLHttpRequest, 0 axios. Les endpoints backend (/api/customers, /api/credits, /api/payments, /api/sync/*) ne sont jamais appelés
- Aucune persistance : 0 localStorage, 0 IndexedDB — rien ne survit a un rafraichissement (offline-first absent dans cette version web)
- Journal / historique des operations par client : absent
- Bouton d'appel telephonique sur les alertes : presents mais sans tel:

## 4. BUGS DETECTES

1. **Bouton "Détails" mal câblé** (vue Clients) : il lance shareWhatsApp au lieu d'afficher les détails du client.
2. **Numéros de téléphone vides** : dans les alertes d'échéance, shareWhatsApp("Moussa Traoré", "", ...) → le lien wa.me/ est généré sans numéro (inutilisable).
3. **Données 100 % codées en dur** : statistiques (145.000 F / 85.500 F / 12 clients / 3 dossiers), clients fictifs (Amadou Diallo, Fatouma Sana...), dates (10 Oct, 25 Oct). Rien ne vient de la base (data/cahier_boutique.db).
4. **clients-retard.html et clients-retard-new.html** : deux copies quasi identiques, entièrement statiques, non reliées à index.html.

## 5. RECOMMANDATIONS (par priorité)

1. **P0 — Brancher l'API** : remplacer les données en dur par des appels fetch aux endpoints existants (/api/customers, /api/credits, /api/payments, /api/sync/status, /api/sync/push).
2. **P0 — Vues CRUD** : formulaires modaux "Ajouter/Modifier Client", "Ajouter/Modifier Crédit", "Enregistrer Paiement" (Espèces / Mobile Money / Virement / Autre).
3. **P1 — Rendre actifs** : filtres crédits, recherche clients, boutons "Appeler" (tel:), "Rappel WhatsApp" avec numéro réel, "Lancer la synchronisation", menu hamburger mobile.
4. **P1 — Vue Paiements** : liste des paiements + mise à jour automatique du statut du crédit.
5. **P2 — Persistance locale** : localStorage/IndexedDB pour l'offline-first, avec file de synchronisation.
6. **P2 — Nettoyage** : unifier clients-retard.html / clients-retard-new.html dans le routing existant ou les supprimer.

---

*Le serveur a été relancé et laissé actif sur http://localhost:8000/ (frontend servi depuis frontend/web/). Le backend FastAPI (qui occupe habituellement ce port) n'était pas démarré pendant le test : il s'agit de deux serveurs distincts partageant le port 8000 — à revoir pour un vrai déploiement.*
## ✅ MISE À JOUR — 09/08/2026 : API branchée & boutons actifs

Le frontend `frontend/web/index.html` a été **entierement reecrit** (meme design Tailwind, donnees dynamiques) et branche sur l'API backend.

### Ce qui est maintenant fonctionnel (valide de bout en bout dans Chrome headless + tests API) :
- **Chargement dynamique** : clients, credits, paiements, statut sync charges depuis l'API (plus aucune donnee en dur).
- **Dashboard** : argent du / paye / nb clients / retards recalcules en temps reel (ex : 12 Clients, 16 000 F dus).
- **Clients** : Ajouter, Modifier, (De)activer, Supprimer, recherche live, Appeler (tel:), Rappel WhatsApp (numero reel).
- **Credits** : Ajouter (client + montant + description + echeance 30j), Modifier (statut/montant/description), Supprimer, filtres Tous/En attente/En retard/Payes, bouton Payer.
- **Paiements** : vue dediee + modal (client, credit, montant, methode Especes/Mobile Money/Virement/Autre, reference) ; le statut du credit se met a jour automatiquement (paye si tout est paye).
- **Synchronisation** : bouton Lancer la synchronisation (POST /api/sync/push), indicateur operations en attente, etat Connecte/Pas de connexion.

### Backend :
- `main.py` : ajout du montage statique du frontend (`CAHIER_SERVE_FRONTEND=true`) pour servir index.html a la racine tout en gardant `/api`, `/health`, `/docs`.
- La route JSON racine est preservee en mode API seule (pas de regression sur les tests).
- Serveur en cours d'ecoute sur http://localhost:8000/ (backend FastAPI + frontend).
