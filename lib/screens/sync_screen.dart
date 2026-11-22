import 'package:flutter/material.dart';

import '../database/sync_queue_dao.dart';
import '../repositories/ecahier_repository.dart';
import '../theme/app_icons.dart';
import '../theme/app_theme.dart';
import '../utils/parsing.dart';
import '../widgets/ecahier_widgets.dart';
import '../widgets/repo_builder.dart';

class SyncScreen extends StatelessWidget {
  const SyncScreen({super.key});

  Future<void> _syncNow(BuildContext context) async {
    final repo = EcahierRepository.instance;
    await repo.sync();
    final status = await repo.getSyncStatus();
    if (!context.mounted) return;
    showSnack(
      context,
      status.lastError ??
          (status.pending == 0
              ? 'Tout est à jour'
              : '${status.pending} élément(s) restent à envoyer'),
    );
  }

  @override
  Widget build(BuildContext context) {
    final repo = EcahierRepository.instance;
    return Scaffold(
      body: RepoBuilder<(Snapshot, SyncStatus)>(
        refreshOn: [repo.syncing],
        load: (r) async => (await r.loadSnapshot(), await r.getSyncStatus()),
        builder: (context, state) {
          final (data, status) = state;
          final colors = Theme.of(context).colorScheme;
          return RefreshIndicator(
            onRefresh: () => repo.sync(),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const ScreenHeader(
                    title: 'Synchronisation',
                    subtitle:
                        'Vos données sont enregistrées sur ce téléphone, '
                        'même sans connexion.',
                  ),
                  const SizedBox(height: 24),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Envoi au serveur',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleLarge
                                  ?.copyWith(color: colors.primary)),
                          const SizedBox(height: 16),
                          _statRow(
                            context,
                            'À envoyer',
                            status.pending == 0
                                ? 'Rien'
                                : '${status.pending}',
                            status.pending == 0
                                ? colors.primary
                                : AppColors.tertiaryText,
                          ),
                          if (status.failed > 0) ...[
                            const SizedBox(height: 10),
                            _statRow(context, 'Refusés par le serveur',
                                '${status.failed}', colors.error),
                          ],
                          const SizedBox(height: 10),
                          _statRow(
                            context,
                            'Dernier envoi réussi',
                            status.lastSyncAt == null
                                ? 'Pas encore'
                                : formatDate(status.lastSyncAt!),
                            colors.onSurfaceVariant,
                          ),
                          if (status.lastError != null) ...[
                            const SizedBox(height: 12),
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Icon(AppIcons.cloudOff,
                                    size: 18, color: colors.error),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(status.lastError!,
                                      style: TextStyle(color: colors.error)),
                                ),
                              ],
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                  if (status.failed > 0) ...[
                    const SizedBox(height: 16),
                    _failedCard(context, repo, status),
                  ],
                  const SizedBox(height: 16),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Sur ce téléphone',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleLarge
                                  ?.copyWith(color: colors.primary)),
                          const SizedBox(height: 16),
                          _statRow(context, 'Clients',
                              '${data.customers.length}', colors.primary),
                          const SizedBox(height: 10),
                          _statRow(context, 'Crédits',
                              '${data.credits.length}', AppColors.tertiaryText),
                          const SizedBox(height: 10),
                          _statRow(context, 'Paiements',
                              '${data.payments.length}', colors.secondary),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
                  ValueListenableBuilder<bool>(
                    valueListenable: repo.syncing,
                    builder: (context, syncing, _) => SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: syncing ? null : () => _syncNow(context),
                        icon: syncing
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                    strokeWidth: 2),
                              )
                            : const Icon(AppIcons.sync),
                        label: Text(syncing
                            ? 'Synchronisation...'
                            : 'Synchroniser maintenant'),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  /// Éléments que le serveur a refusés : visibles, jamais perdus.
  Widget _failedCard(
      BuildContext context, EcahierRepository repo, SyncStatus status) {
    final colors = Theme.of(context).colorScheme;
    return Card(
      color: colors.errorContainer.withValues(alpha: 0.3),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Non envoyés',
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(color: colors.error)),
            const SizedBox(height: 8),
            for (final entry in status.failedEntries.take(5))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Text(
                  '${_label(entry)} : ${entry.lastError ?? 'refusé'}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            if (status.failedEntries.length > 5)
              Text('… et ${status.failedEntries.length - 5} autres',
                  style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 8),
            TextButton.icon(
              onPressed: () => repo.retryFailed(),
              icon: const Icon(AppIcons.sync, size: 18),
              label: const Text('Réessayer'),
            ),
          ],
        ),
      ),
    );
  }

  String _label(SyncEntry entry) {
    switch (entry.tableName) {
      case 'customers':
        return 'Client';
      case 'credits':
        return 'Crédit';
      case 'payments':
        return 'Paiement';
      default:
        return entry.tableName;
    }
  }

  Widget _statRow(
      BuildContext context, String label, String value, Color color) {
    // Le libellé peut passer sur 2 lignes quand le texte est agrandi ; la
    // valeur reste alignée à droite.
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Text(label,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant)),
        ),
        const SizedBox(width: 12),
        Flexible(
          child: Text(value,
              textAlign: TextAlign.end,
              style: TextStyle(color: color, fontWeight: FontWeight.w700)),
        ),
      ],
    );
  }
}
