/// Centralise les icônes de l'application Ecahier.
///
/// Icônes Material livrées avec Flutter : aucun paquet d'icônes supplémentaire
/// (l'ancien `lucide_icons` ne compile plus avec Flutter 3.47, et chaque
/// paquet alourdit l'APK sur des téléphones modestes). Les glyphes inutilisés
/// sont retirés automatiquement du build release.
library;

import 'package:flutter/material.dart';

class AppIcons {
  // --- Navigation ---
  static const IconData dashboard = Icons.dashboard_outlined;
  static const IconData customers = Icons.people_outline;
  static const IconData credits = Icons.receipt_long_outlined;
  static const IconData payments = Icons.account_balance_wallet_outlined;
  static const IconData sync = Icons.sync;

  // --- Formulaires / actions ---
  static const IconData add = Icons.add;
  static const IconData search = Icons.search;
  static const IconData user = Icons.person_outline;
  static const IconData phone = Icons.phone_outlined;
  static const IconData place = Icons.place_outlined;
  static const IconData calendar = Icons.calendar_today_outlined;
  static const IconData info = Icons.info_outline;
  static const IconData money = Icons.payments_outlined;
  static const IconData pause = Icons.pause_circle_outline;
  static const IconData note = Icons.notes;

  // --- Statuts / alertes ---
  static const IconData warning = Icons.warning_amber_rounded;
  static const IconData checkCircle = Icons.check_circle_outline;
  static const IconData cloudOff = Icons.cloud_off_outlined;

  // --- Méthodes de paiement ---
  static const IconData cash = Icons.money;
  static const IconData mobileMoney = Icons.smartphone;
  static const IconData bankTransfer = Icons.account_balance_outlined;
  static const IconData other = Icons.more_horiz;
}
