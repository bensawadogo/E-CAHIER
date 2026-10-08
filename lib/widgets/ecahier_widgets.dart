/// Widgets et utilitaires partagés pour l'application Ecahier.
/// Centralise les éléments récurrents pour un style moderne et épuré.
library;

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../theme/app_icons.dart';
import '../theme/app_theme.dart';

// ---------------------------------------------------------------------------
// Utilitaires de formatage
// ---------------------------------------------------------------------------

/// Décoration d'entrée standard "moderne et épuré" (champs de formulaire).
/// Utilisée par les écrans clients, crédits et paiements.
InputDecoration modernInputDecoration(
  String label, {
  String? hint,
  IconData? icon,
}) {
  return InputDecoration(
    labelText: label,
    hintText: hint,
    prefixIcon: icon != null ? Icon(icon, size: 20) : null,
    filled: true,
    fillColor: AppColors.surfaceContainerLow,
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(AppColors.buttonRadius),
      borderSide: BorderSide.none,
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(AppColors.buttonRadius),
      borderSide: const BorderSide(color: AppColors.surfaceContainerHigh),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(AppColors.buttonRadius),
      borderSide: const BorderSide(color: AppColors.primary, width: 2),
    ),
  );
}

/// Formate un montant en FCFA avec séparateurs de milliers.
/// Reçoit les centimes (int) et convertit en unités monétaires.
String formatCurrency(int centimes) {
  final fcfa = centimes / 100;
  return NumberFormat.currencyPattern('fr', 'XOF').format(fcfa);
}

/// Couleur d'avatar déterministe dérivée du nom.
Color avatarColor(String name) {
  final seed = name.isNotEmpty
      ? name.codeUnits.fold<int>(0, (a, b) => a + b)
      : 0;
  const palette = [
    Color(0xFFB3261E),
    Color(0xFF825500),
    Color(0xFF3B6200),
    Color(0xFF006B5E),
    Color(0xFF0061A4),
    Color(0xFF6D5D8B),
    Color(0xFF7B5700),
    Color(0xFF00696D),
  ];
  return palette[seed % palette.length];
}

/// Libellé humain pour la méthode de paiement.
String paymentMethodLabel(String method) {
  switch (method) {
    case 'cash':
      return 'Espèces';
    case 'mobile_money':
      return 'Mobile Money';
    case 'bank_transfer':
      return 'Virement';
    default:
      return 'Autre';
  }
}

/// Icône correspondant à la méthode de paiement (jeux d'icônes réels).
IconData paymentMethodIcon(String method) {
  switch (method) {
    case 'cash':
      return AppIcons.cash;
    case 'mobile_money':
      return AppIcons.mobileMoney;
    case 'bank_transfer':
      return AppIcons.bankTransfer;
    default:
      return AppIcons.other;
  }
}

/// Libellé humain pour le statut d'un crédit.
String creditStatusLabel(String status) {
  switch (status) {
    case 'paid':
      return 'Payé';
    case 'active':
      return 'Actif';
    default:
      return 'Inconnu';
  }
}

/// Initiales du nom pour l'avatar circulaire.
String nameInitials(String name) {
  final parts = name.trim().split(RegExp(r'\s+'));
  if (parts.isEmpty) return '?';
  if (parts.length == 1) {
    return parts[0].isNotEmpty ? parts[0][0] : '?';
  }
  return parts[0][0] + parts[parts.length - 1][0];
}

// ---------------------------------------------------------------------------
// Widgets réutilisables
// ---------------------------------------------------------------------------

/// Carte de statistiques moderne — utilisée sur le dashboard.
class StatCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color color;
  final Color? backgroundColor;

  const StatCard({
    super.key,
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
    this.backgroundColor,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final isDarkOnBg = backgroundColor != null &&
        backgroundColor!.computeLuminance() < 0.5;

    return Card(
      elevation: 0,
      color: backgroundColor ?? colors.surfaceContainerLow,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppColors.borderRadius),
        side: BorderSide(
          color: isDarkOnBg
              ? Colors.transparent
              : colors.outlineVariant.withOpacity(0.5),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: color.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: color, size: 22),
                ),
                Text(
                  title,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: isDarkOnBg
                            ? Colors.white70
                            : colors.onSurfaceVariant,
                        fontWeight: FontWeight.w600,
                      ),
                ),
                             ],
            ),
            const SizedBox(height: 10),
            Text(
              value,
              style: Theme.of(context)
                  .textTheme
                  .headlineMedium
                  ?.copyWith(
                    color: isDarkOnBg ? Colors.white : color,
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Badge circulaire coloré pour le statut d'un crédit.
class StatusBadge extends StatelessWidget {
  final String label;
  final Color color;

  const StatusBadge({
    super.key,
    required this.label,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 12,
          color: color,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

/// En-tête de section moderne avec titre et compteur optionnel.
class SectionHeader extends StatelessWidget {
  final String title;
  final int? count;
  final IconData? icon;

  const SectionHeader({
    super.key,
    required this.title,
    this.count,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
      child: Row(
        children: [
          if (icon != null) ...[
            Icon(icon, color: colors.primary, size: 20),
            const SizedBox(width: 6),
          ],
          Text(
            title,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: colors.onSurface.withOpacity(0.7),
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(width: 8),
          if (count != null)
            Container(
              padding: const EdgeInsets.symmetric(
                  horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: colors.primary.withOpacity(0.12),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Text(
                '$count',
                style: TextStyle(
                  fontSize: 12,
                  color: colors.primary,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

/// Message d'état vide moderne.
class EmptyState extends StatelessWidget {
  final IconData icon;
  final String message;

  const EmptyState({
    super.key,
    required this.icon,
    required this.message,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 56, color: colors.onSurfaceVariant),
            const SizedBox(height: 16),
            Text(
              message,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: colors.onSurfaceVariant,
                  ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

/// Message d'état d'erreur moderne avec bouton de réessai.
class ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;

  const ErrorState({
    super.key,
    required this.message,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 56, color: colors.error),
            const SizedBox(height: 16),
            Text(
              message,
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: colors.onSurfaceVariant),
              textAlign: TextAlign.center,
            ),
            if (onRetry != null) ...[
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh, size: 18),
                label: const Text('Réessayer'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

