# 🎨 PROMPT POUR STITCH — DESIGN DU SITE CAHIER BOUTIQUE

Copie ce prompt en entier et envoie-le à Stitch. Il est déjà adapté au contexte du Burkina Faso et à toutes les fonctionnalités du backend.

---

## PROMPT (copie tout ce qui suit)

Crée-moi un site web complet pour une boutique au Burkina Faso qui vend à crédit. Le site s'appelle "Cahier Boutique". C'est pour un petit commerçant qui n'a pas fait l'école, qui parle un français simple, et qui utilise un téléphone pas cher avec une connexion internet faible (2G/3G). Le site doit être TRÈS simple à utiliser, avec de GROS boutons et de GROS textes.

**IMPORTANT : Génère TOUT le site dans UN SEUL bloc de code (un seul fichier HTML avec le CSS et le JavaScript dedans). Ne sépare pas le code en plusieurs morceaux. Je dois pouvoir tout copier d'un coup.**

### Le design (très important)
- PAS de couleurs primaires criardes (pas de bleu vif, pas de rouge vif, pas de vert flashy). Ça fait "site fait par une machine".
- Utilise des couleurs chaudes et naturelles qui rappellent l'Afrique : terre cuite, ocre, sable, vert doux, orange doux, marron. Un fond crème/sable clair.
- Le style doit être chaleureux, simple, artisanal. Comme un vrai cahier de boutique papier mais en version numérique.
- Police simple et lisible, pas trop petite (minimum 16px pour le texte).
- Les boutons doivent être gros et faciles à taper avec le doigt.
- Le site doit être léger et rapide, même sur un vieux téléphone. Pas d'images lourdes, pas d'animations compliquées.
- Tout doit fonctionner en français simple, avec des mots faciles.

### Les pages et fonctionnalités (toutes doivent être dans le site)

**1. Page d'accueil (tableau de bord)**
- Un grand chiffre : le total d'argent que les clients doivent (le solde total).
- Un grand chiffre : le total d'argent déjà payé.
- Le nombre de clients.
- Le nombre de crédits en retard (les clients qui n'ont pas payé à temps).
- Des gros boutons pour aller vers : Clients, Crédits, Paiements.

**2. Page Clients**
- Une liste de tous les clients avec leur nom et leur solde (combien ils doivent).
- Un bouton "Ajouter un client" qui ouvre un petit formulaire (nom, téléphone, adresse, notes).
- Un champ de recherche pour trouver un client par son nom.
- Pouvoir modifier un client (changer son nom, téléphone, etc.).
- Pouvoir désactiver un client (le mettre inactif) sans le supprimer.
- Pouvoir supprimer un client.
- Chaque client doit montrer : combien il doit au total, combien il a payé, et son solde restant.

**3. Page Crédits**
- Une liste de tous les crédits (les dettes des clients).
- Un bouton "Ajouter un crédit" : choisir le client, mettre le montant en FCFA, une description (ex: "marchandises"), et la date d'échéance (par défaut 30 jours).
- Chaque crédit montre : le client, le montant, le statut (en attente, partiellement payé, payé, annulé), et s'il est en retard.
- Pouvoir filtrer : voir seulement les crédits en attente, ou seulement ceux en retard.
- Pouvoir modifier un crédit (montant, statut, date).
- Pouvoir supprimer un crédit.

**4. Page Paiements**
- Un bouton "Enregistrer un paiement" : choisir le client, choisir le crédit, mettre le montant en FCFA, choisir la méthode (Espèces, Mobile Money, Virement, Autre), et une référence si besoin.
- Une liste de tous les paiements avec la date, le client, le montant et la méthode.
- Quand on paie un crédit, le statut du crédit doit se mettre à jour tout seul (payé si tout est payé, partiellement payé sinon).

**5. Page Synchronisation**
- Un bouton "Synchroniser" pour envoyer les données au serveur quand il y a internet.
- Un indicateur du nombre d'opérations en attente de synchronisation.
- Un message simple : "Connecté" ou "Pas de connexion".

### Comment ça marche (pour que tu comprennes)
- Le site fonctionne même sans internet : tout est enregistré sur le téléphone d'abord.
- Quand il y a internet, on peut synchroniser avec le serveur.
- Les montants sont en FCFA (francs CFA).
- Les méthodes de paiement : Espèces (cash), Mobile Money (comme Orange Money, Moov Money), Virement bancaire, Autre.

### Ce que je veux absolument
- Un site qui a l'air fait pour l'Afrique, pas un site générique.
- Simple, gros boutons, gros textes, facile pour quelqu'un qui n'a pas fait l'école.
- Rapide et léger pour un vieux téléphone.
- TOUT dans un seul bloc de code que je peux copier d'un coup.

---

## 📋 RAPPEL DES FONCTIONNALITÉS DU BACKEND (pour vérifier que rien ne manque)

| Fonctionnalité | Détail |
|---|---|
| Clients | Ajouter, modifier, désactiver, supprimer, rechercher par nom, voir solde |
| Crédits | Ajouter, modifier, supprimer, statuts (en attente / partiel / payé / annulé), détection retard |
| Paiements | Enregistrer (Espèces, Mobile Money, Virement, Autre), liste, mise à jour auto du crédit |
| Journal | Historique des opérations par client |
| Sync | Bouton synchroniser, compteur d'opérations en attente, mode hors-ligne |
| Montants | En FCFA |
| Contexte | Burkina Faso, connexion faible, téléphone bas de gamme, français simple | n