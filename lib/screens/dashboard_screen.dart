import 'package:flutter/material.dart';

import '../models/credit.dart';
import '../models/customer.dart';
import '../repositories/ecahier_repository.dart';
import '../theme/app_icons.dart';
import '../theme/app_theme.dart';
import '../utils/parsing.dart';
import '../widgets/ecahier_widgets.dart';
import '../widgets/repo_builder.dart';

/// Nombre maximum de lignes affichées dans chaque liste du tableau de bord
/// (les listes complètes sont dans les autres onglets).
const int _maxRows = 5;

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return RepoBuilder<Snapshot>(
      load: (repo) => repo.loadSnapshot(),
      builder: (context, data) {
        final colors = Theme.of(context).colorScheme;
        final overdue = data.credits.where((c) => c.isOverdue()).toList()
          ..sort((a, b) => a.dueDate!.compareTo(b.dueDate!));
        final recent = [...data.customers]
          ..sort((a, b) => b.createdAt.compareTo(a.createdAt));

        return RefreshIndicator(
          onRefresh: () => EcahierRepository.instance.sync(),
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const ScreenHeader(
                  title: 'Tableau de bord',
                  subtitle: 'Suivi de votre caisse',
                ),
                const SizedBox(height: 24),
                // Deux rangées à hauteur adaptée au contenu : une grille à
                // proportion fixe débordait dès que le texte était agrandi.
                _statRow(
                  StatCard(
                    title: 'Clients',
                    value: '${data.customers.length}',
                    icon: AppIcons.user,
                    color: colors.primary,
                  ),
                  StatCard(
                    title: 'Crédits',
                    value: '${data.credits.length}',
                    icon: AppIcons.credits,
                    color: AppColors.tertiaryText,
                  ),
                ),
                const SizedBox(height: 12),
                _statRow(
                  StatCard(
                    title: 'Paiements',
                    value: '${data.payments.length}',
                    icon: AppIcons.payments,
                    color: colors.secondary,
                  ),
                  StatCard(
                    title: 'En retard',
                    value: '${overdue.length}',
                    icon: AppIcons.warning,
                    color: colors.error,
                    backgroundColor:
                        colors.errorContainer.withValues(alpha: 0.3),
                  ),
                ),
                const SizedBox(height: 24),
                const SectionHeader(
                    title: 'Derniers clients', icon: AppIcons.user),
                if (recent.isEmpty)
                  const EmptyState(
                    icon: AppIcons.user,
                    message: 'Aucun client enregistré.',
                  )
                else
                  _rows(
                    context,
                    recent.take(_maxRows).map((c) => _customerRow(context, c)),
                  ),
                const SizedBox(height: 16),
                SectionHeader(
                  title: 'Crédits en retard',
                  icon: AppIcons.warning,
                  count: overdue.isEmpty ? null : overdue.length,
                ),
                if (overdue.isEmpty)
                  const EmptyState(
                    icon: AppIcons.checkCircle,
                    message: 'Aucun crédit en retard.',
                  )
                else ...[
                  _rows(
                    context,
                    overdue
                        .take(_maxRows)
                        .map((c) => _overdueRow(context, data, c)),
                  ),
                  if (overdue.length > _maxRows)
                    Padding(
                      padding: const EdgeInsets.only(top: 8, left: 4),
                      child: Text(
                        '+ ${overdue.length - _maxRows} autres dans l\'onglet Crédits',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: colors.onSurfaceVariant),
                      ),
                    ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _statRow(Widget left, Widget right) => IntrinsicHeight(
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Expanded(child: left),
            const SizedBox(width: 12),
            Expanded(child: right),
          ],
        ),
      );

  /// Carte contenant quelques lignes (pas de ListView : maximum 5 lignes).
  Widget _rows(BuildContext context, Iterable<Widget> rows) {
    final children = <Widget>[];
    for (final row in rows) {
      if (children.isNotEmpty) {
        children.add(const Divider(height: 1, indent: 72));
      }
      children.add(row);
    }
    return Card(child: Column(children: children));
  }

  Widget _customerRow(BuildContext context, Customer c) {
    final colors = Theme.of(context).colorScheme;
    return ListTile(
      leading: CustomerAvatar(name: c.name),
      title: Text(c.name),
      subtitle: Text((c.phone ?? '').isEmpty ? '—' : c.phone!),
      trailing: Text(
        formatDate(c.createdAt),
        style: Theme.of(context)
            .textTheme
            .bodySmall
            ?.copyWith(color: colors.onSurfaceVariant),
      ),
    );
  }

  Widget _overdueRow(BuildContext context, Snapshot data, Credit credit) {
    final colors = Theme.of(context).colorScheme;
    final customer = data.customerOf(credit.customerId);
    return ListTile(
      leading: CircleAvatar(
        backgroundColor: colors.error.withValues(alpha: 0.12),
        child: Icon(AppIcons.credits, color: colors.error),
      ),
      title: Text(customer.name, style: TextStyle(color: colors.error)),
      subtitle: Text(
        'Reste ${formatCurrency(data.remaining(credit))}',
        style: TextStyle(color: colors.error, fontWeight: FontWeight.w600),
      ),
      trailing: Text(
        formatDate(credit.dueDate!),
        style: Theme.of(context)
            .textTheme
            .bodySmall
            ?.copyWith(color: colors.onSurfaceVariant),
      ),
    );
  }
}
