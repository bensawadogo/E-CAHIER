/// Widgets et utilitaires partagés pour l'application Ecahier.
library;

import 'package:flutter/material.dart';

import '../theme/app_icons.dart';
import '../theme/app_theme.dart';

// ---------------------------------------------------------------------------
// Utilitaires
// ---------------------------------------------------------------------------

/// Décoration d'entrée standard (champs de formulaire).
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

/// Couleur d'avatar déterministe dérivée du nom.
Color avatarColor(String name) {
  final seed =
      name.isNotEmpty ? name.codeUnits.fold<int>(0, (a, b) => a + b) : 0;
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

/// Icône correspondant à la méthode de paiement.
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
    case 'pending':
      return 'En attente';
    case 'partial':
      return 'Partiel';
    case 'paid':
      return 'Payé';
    case 'cancelled':
      return 'Annulé';
    default:
      return 'Inconnu';
  }
}

/// Initiales du nom pour l'avatar circulaire.
String nameInitials(String name) {
  final parts =
      name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
  if (parts.isEmpty) return '?';
  if (parts.length == 1) return parts[0][0].toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/// Message court en bas d'écran.
void showSnack(BuildContext context, String message) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(message)));
}

// ---------------------------------------------------------------------------
// Widgets réutilisables
// ---------------------------------------------------------------------------

/// Titre d'écran avec sous-titre optionnel.
class ScreenHeader extends StatelessWidget {
  final String title;
  final String? subtitle;

  const ScreenHeader({super.key, required this.title, this.subtitle});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title,
            style: theme.textTheme.headlineLarge
                ?.copyWith(fontWeight: FontWeight.w700)),
        if (subtitle != null) ...[
          const SizedBox(height: 4),
          Text(subtitle!,
              style: theme.textTheme.bodyMedium
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant)),
        ],
      ],
    );
  }
}

/// Avatar rond avec les initiales du client.
class CustomerAvatar extends StatelessWidget {
  final String name;
  final double radius;

  const CustomerAvatar({super.key, required this.name, this.radius = 22});

  @override
  Widget build(BuildContext context) {
    return CircleAvatar(
      radius: radius,
      backgroundColor: avatarColor(name),
      child: Text(
        nameInitials(name),
        style: TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.bold,
            fontSize: radius * 0.75),
      ),
    );
  }
}

/// Ligne « icône + texte » des fenêtres de détail.
class InfoRow extends StatelessWidget {
  final IconData icon;
  final String text;

  const InfoRow({super.key, required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    final color = Theme.of(context).colorScheme.onSurfaceVariant;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 10),
          Expanded(child: Text(text, style: TextStyle(color: color))),
        ],
      ),
    );
  }
}

/// Carte de statistiques — utilisée sur le tableau de bord.
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
    final isDarkOnBg =
        backgroundColor != null && backgroundColor!.computeLuminance() < 0.5;

    return Card(
      elevation: 0,
      color: backgroundColor ?? colors.surfaceContainerLow,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppColors.borderRadius),
        side: BorderSide(
          color: isDarkOnBg
              ? Colors.transparent
              : colors.outlineVariant.withValues(alpha: 0.5),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: color, size: 22),
                ),
                const SizedBox(width: 8),
                // Texte agrandi sur un petit écran : on tronque le titre au
                // lieu de déborder.
                Expanded(
                  child: Text(
                    title,
                    textAlign: TextAlign.end,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: isDarkOnBg
                              ? Colors.white70
                              : colors.onSurfaceVariant,
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            // Un très grand nombre rétrécit plutôt que de déborder.
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(
                value,
                maxLines: 1,
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      color: isDarkOnBg ? Colors.white : color,
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Ligne de liste (carte) qui supporte les gros textes et les petits écrans.
///
/// Un `ListTile` impose une hauteur et une largeur de contenu serrées : avec le
/// texte agrandi par l'utilisateur, le montant à droite « consomme toute la
/// largeur » et la mise en page plante. Ici le titre/sous-titre se partagent
/// la place et peuvent passer sur plusieurs lignes ; la zone de droite est
/// plafonnée.
class RecordTile extends StatelessWidget {
  final Widget leading;
  final Widget title;
  final Widget? subtitle;
  final Widget? trailing;
  final VoidCallback? onTap;

  const RecordTile({
    super.key,
    required this.leading,
    required this.title,
    this.subtitle,
    this.trailing,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              leading,
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    title,
                    if (subtitle != null) ...[
                      const SizedBox(height: 2),
                      subtitle!,
                    ],
                  ],
                ),
              ),
              if (trailing != null) ...[
                const SizedBox(width: 8),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 132),
                  child: trailing,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Badge coloré pour le statut d'un crédit.
class StatusBadge extends StatelessWidget {
  final String label;
  final Color color;

  const StatusBadge({super.key, required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        label,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style:
            TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w600),
      ),
    );
  }
}

/// En-tête de section avec titre et compteur optionnel.
class SectionHeader extends StatelessWidget {
  final String title;
  final int? count;
  final IconData? icon;

  const SectionHeader({super.key, required this.title, this.count, this.icon});

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
          Flexible(
            child: Text(
              title,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: colors.onSurface.withValues(alpha: 0.7),
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
          const SizedBox(width: 8),
          if (count != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: colors.primary.withValues(alpha: 0.12),
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

/// Message d'état vide.
class EmptyState extends StatelessWidget {
  final IconData icon;
  final String message;

  const EmptyState({super.key, required this.icon, required this.message});

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
              style: Theme.of(context)
                  .textTheme
                  .bodyMedium
                  ?.copyWith(color: colors.onSurfaceVariant),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

/// Message d'erreur avec bouton de réessai.
class ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback? onRetry;

  const ErrorState({super.key, required this.message, this.onRetry});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(AppIcons.warning, size: 56, color: colors.error),
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
                icon: const Icon(AppIcons.sync, size: 18),
                label: const Text('Réessayer'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
