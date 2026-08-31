/// Centralise les icônes de l'application Ecahier.
///
/// On utilise des JEUX D'ICÔNES RÉELS et open source (pas de glyphes générés
/// par IA) :
///   - **Lucide** (lucide.dev) : lignes nettes et cohérentes pour l'UI.
///   - **Font Awesome** (fontawesome.com) : compléments (paiement, marques).
///
/// Centraliser ici permet de garder une correspondance cohérente et
/// facile à maintenir.
library;

import 'package:flutter/material.dart';
import 'package:font_awesome_flutter/font_awesome_flutter.dart';
import 'package:lucide_icons/lucide_icons.dart';

/// Icônes d'écran / navigation (Lucide).
class AppIcons {
  // --- Navigation ---
  static const IconData dashboard = LucideIcons.layoutDashboard;
  static const IconData customers = LucideIcons.users;
  static const IconData credits = LucideIcons.creditCard;
  static const IconData payments = LucideIcons.wallet;
  static const IconData sync = LucideIcons.refreshCw;

  // --- Formulaires / actions ---
  static const IconData add = LucideIcons.plus;
  static const IconData search = LucideIcons.search;
  static const IconData user = LucideIcons.user;
  static const IconData phone = LucideIcons.phone;
  static const IconData place = LucideIcons.mapPin;
  static const IconData calendar = LucideIcons.calendar;
  static const IconData info = LucideIcons.info;
  static const IconData money = LucideIcons.banknote;
  static const IconData pause = LucideIcons.pause;

  // --- Statuts / alertes ---
  static const IconData warning = LucideIcons.alertTriangle;
  static const IconData checkCircle = LucideIcons.checkCircle;

  // --- Méthodes de paiement (Font Awesome fait le lien avec le réel) ---
  static const IconData cash = FontAwesomeIcons.coins; // espèces
  static const IconData mobileMoney = FontAwesomeIcons.mobileScreenButton; // mobile money
  static const IconData bankTransfer = FontAwesomeIcons.buildingColumns; // virement
  static const IconData other = FontAwesomeIcons.creditCard; // autre / carte
}
