import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/credit.dart';
import '../models/customer.dart';
import '../repositories/ecahier_repository.dart';
import '../theme/app_icons.dart';
import '../theme/app_theme.dart';
import '../utils/parsing.dart';
import '../widgets/ecahier_widgets.dart';
import '../widgets/repo_builder.dart';

class CreditsScreen extends StatelessWidget {
  const CreditsScreen({super.key});

  Future<void> _showAddDialog(BuildContext context) async {
    final customers = await EcahierRepository.instance.getCustomers();
    if (!context.mounted) return;
    if (customers.isEmpty) {
      showSnack(context, "Ajoutez d'abord un client.");
      return;
    }
    final created = await showDialog<bool>(
      context: context,
      builder: (_) => _CreditFormDialog(customers: customers),
    );
    if (created == true && context.mounted) {
      showSnack(context, 'Crédit enregistré');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: RepoBuilder<Snapshot>(
        load: (repo) => repo.loadSnapshot(),
        builder: (context, data) {
          final toCollect = data.credits
              .where((c) => c.isOpen)
              .fold<int>(0, (sum, c) => sum + data.remaining(c));
          // L'en-tête défile avec la liste : fixe, il mangeait la moitié de
          // l'écran quand le texte est agrandi.
          final header = Padding(
            padding: const EdgeInsets.fromLTRB(0, 24, 0, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const ScreenHeader(title: 'Crédits'),
                const SizedBox(height: 16),
                Text(
                  'Reste à encaisser : ${formatCurrency(toCollect)}',
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.w600),
                ),
              ],
            ),
          );
          return RefreshIndicator(
            onRefresh: () => EcahierRepository.instance.sync(),
            child: ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.fromLTRB(24, 0, 24, 96),
              itemCount: data.credits.isEmpty ? 2 : data.credits.length + 1,
              itemBuilder: (context, i) {
                if (i == 0) return header;
                if (data.credits.isEmpty) {
                  return const EmptyState(
                    icon: AppIcons.credits,
                    message: 'Aucun crédit.\nAppuyez sur + pour en ajouter.',
                  );
                }
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _creditTile(context, data, data.credits[i - 1]),
                );
              },
            ),
          );
        },
      ),
      floatingActionButton: FloatingActionButton(
        tooltip: 'Nouveau crédit',
        onPressed: () => _showAddDialog(context),
        child: const Icon(AppIcons.add),
      ),
    );
  }

  Widget _creditTile(BuildContext context, Snapshot data, Credit credit) {
    final colors = Theme.of(context).colorScheme;
    final customer = data.customerOf(credit.customerId);
    final overdue = credit.isOverdue();
    final Color accent = credit.status == CreditStatus.paid
        ? colors.primary
        : (overdue ? colors.error : AppColors.tertiaryText);
    final label = overdue ? 'En retard' : creditStatusLabel(credit.status);

    return RecordTile(
      leading: CustomerAvatar(name: customer.name),
      title: Text(customer.name,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Text(
        credit.isOpen
            ? 'Reste ${formatCurrency(data.remaining(credit))} '
                'sur ${formatCurrency(credit.amount)}'
            : formatCurrency(credit.amount),
        style: TextStyle(color: accent, fontWeight: FontWeight.w600),
      ),
      trailing: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          StatusBadge(label: label, color: accent),
          if (credit.dueDate != null) ...[
            const SizedBox(height: 4),
            Text(
              formatDate(credit.dueDate!),
              style: Theme.of(context)
                  .textTheme
                  .bodySmall
                  ?.copyWith(color: colors.onSurfaceVariant),
            ),
          ],
        ],
      ),
      onTap: () => _showCreditDetail(context, data, credit, customer),
    );
  }

  void _showCreditDetail(
      BuildContext context, Snapshot data, Credit credit, Customer customer) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppColors.borderRadius)),
        title: Text(customer.name,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            InfoRow(
                icon: AppIcons.money,
                text: 'Montant : ${formatCurrency(credit.amount)}'),
            InfoRow(
                icon: AppIcons.checkCircle,
                text: 'Reste à payer : '
                    '${formatCurrency(data.remaining(credit))}'),
            if (credit.dueDate != null)
              InfoRow(
                  icon: AppIcons.calendar,
                  text: 'Échéance : ${formatDate(credit.dueDate!)}'),
            InfoRow(
                icon: AppIcons.info,
                text: 'Statut : ${creditStatusLabel(credit.status)}'),
            if (credit.description.isNotEmpty)
              InfoRow(icon: AppIcons.note, text: credit.description),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Fermer')),
        ],
      ),
    );
  }
}

/// Formulaire « Nouveau crédit ».
class _CreditFormDialog extends StatefulWidget {
  final List<Customer> customers;

  const _CreditFormDialog({required this.customers});

  @override
  State<_CreditFormDialog> createState() => _CreditFormDialogState();
}

class _CreditFormDialogState extends State<_CreditFormDialog> {
  static const _dueChoices = [7, 15, 30, 60];

  final _form = GlobalKey<FormState>();
  final _amount = TextEditingController();
  final _description = TextEditingController();
  String? _customerId;
  int _dueInDays = 30;
  bool _saving = false;

  @override
  void dispose() {
    _amount.dispose();
    _description.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await EcahierRepository.instance.createCredit(
        customerId: _customerId!,
        amount: parseAmountInput(_amount.text)!,
        description: _description.text,
        dueDate: DateTime.now().add(Duration(days: _dueInDays)),
      );
      if (mounted) Navigator.pop(context, true);
    } on RepositoryException catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      showSnack(context, e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppColors.borderRadius)),
      title: const Text('Nouveau crédit'),
      content: Form(
        key: _form,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              DropdownButtonFormField<String>(
                initialValue: _customerId,
                isExpanded: true,
                decoration: modernInputDecoration('Client', icon: AppIcons.user),
                items: [
                  for (final c in widget.customers)
                    DropdownMenuItem(
                      value: c.id,
                      child: Text(c.name, overflow: TextOverflow.ellipsis),
                    ),
                ],
                onChanged: (v) => setState(() => _customerId = v),
                validator: (v) => v == null ? 'Choisissez un client' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _amount,
                decoration: modernInputDecoration('Montant (FCFA)',
                    icon: AppIcons.money),
                keyboardType: TextInputType.number,
                inputFormatters: [
                  FilteringTextInputFormatter.allow(RegExp(r'[0-9 .,]')),
                  LengthLimitingTextInputFormatter(12),
                ],
                validator: (v) => parseAmountInput(v ?? '') == null
                    ? 'Entrez un montant supérieur à 0'
                    : null,
              ),
              const SizedBox(height: 16),
              Text('À rembourser dans',
                  style: Theme.of(context).textTheme.labelLarge),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: [
                  for (final days in _dueChoices)
                    ChoiceChip(
                      label: Text('$days jours'),
                      selected: _dueInDays == days,
                      onSelected: (_) => setState(() => _dueInDays = days),
                    ),
                ],
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _description,
                decoration: modernInputDecoration('Description (facultatif)',
                    icon: AppIcons.note),
                inputFormatters: [LengthLimitingTextInputFormatter(500)],
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
            onPressed: _saving ? null : () => Navigator.pop(context),
            child: const Text('Annuler')),
        FilledButton(
            onPressed: _saving ? null : _save,
            child: const Text('Enregistrer')),
      ],
    );
  }
}
