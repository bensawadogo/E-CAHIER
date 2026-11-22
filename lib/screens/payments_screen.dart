import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/credit.dart';
import '../models/customer.dart';
import '../models/payment.dart';
import '../repositories/ecahier_repository.dart';
import '../theme/app_icons.dart';
import '../theme/app_theme.dart';
import '../utils/parsing.dart';
import '../widgets/ecahier_widgets.dart';
import '../widgets/repo_builder.dart';

class PaymentsScreen extends StatelessWidget {
  const PaymentsScreen({super.key});

  Future<void> _showAddDialog(BuildContext context) async {
    final data = await EcahierRepository.instance.loadSnapshot();
    if (!context.mounted) return;
    final open = data.credits.where((c) => data.remaining(c) > 0 && c.isOpen);
    if (open.isEmpty) {
      showSnack(context, "Aucun crédit à rembourser pour l'instant.");
      return;
    }
    final created = await showDialog<bool>(
      context: context,
      builder: (_) => _PaymentFormDialog(data: data, openCredits: open.toList()),
    );
    if (created == true && context.mounted) {
      showSnack(context, 'Paiement enregistré');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: RepoBuilder<Snapshot>(
        load: (repo) => repo.loadSnapshot(),
        builder: (context, data) {
          final total = data.payments.fold<int>(0, (sum, p) => sum + p.amount);
          // L'en-tête défile avec la liste (voir l'écran des crédits).
          final header = Padding(
            padding: const EdgeInsets.fromLTRB(0, 24, 0, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const ScreenHeader(title: 'Paiements'),
                const SizedBox(height: 16),
                Text(
                  'Total perçu : ${formatCurrency(total)}',
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
              itemCount: data.payments.isEmpty ? 2 : data.payments.length + 1,
              itemBuilder: (context, i) {
                if (i == 0) return header;
                if (data.payments.isEmpty) {
                  return const EmptyState(
                    icon: AppIcons.payments,
                    message: 'Aucun paiement.\nAppuyez sur + pour en ajouter.',
                  );
                }
                final payment = data.payments[i - 1];
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: _paymentTile(
                      context, payment, data.customerOf(payment.customerId)),
                );
              },
            ),
          );
        },
      ),
      floatingActionButton: FloatingActionButton(
        tooltip: 'Nouveau paiement',
        onPressed: () => _showAddDialog(context),
        child: const Icon(AppIcons.add),
      ),
    );
  }

  Widget _paymentTile(
      BuildContext context, Payment payment, Customer customer) {
    final colors = Theme.of(context).colorScheme;
    return RecordTile(
      leading: CustomerAvatar(name: customer.name),
      title: Text(customer.name,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Row(
        children: [
          Icon(paymentMethodIcon(payment.method),
              size: 16, color: colors.onSurfaceVariant),
          const SizedBox(width: 4),
          Flexible(
            child: Text(paymentMethodLabel(payment.method),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(color: colors.onSurfaceVariant)),
          ),
        ],
      ),
      trailing: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          // Un gros montant rétrécit au lieu de déborder.
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerRight,
            child: Text('+${formatCurrency(payment.amount)}',
                maxLines: 1,
                style: TextStyle(
                    color: colors.primary, fontWeight: FontWeight.w700)),
          ),
          Text(
            formatDate(payment.createdAt),
            style: Theme.of(context)
                .textTheme
                .bodySmall
                ?.copyWith(color: colors.onSurfaceVariant),
          ),
        ],
      ),
      onTap: () => _showPaymentDetail(context, payment, customer),
    );
  }

  void _showPaymentDetail(
      BuildContext context, Payment payment, Customer customer) {
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
                text: 'Montant : +${formatCurrency(payment.amount)}'),
            InfoRow(
                icon: paymentMethodIcon(payment.method),
                text: 'Méthode : ${paymentMethodLabel(payment.method)}'),
            InfoRow(
                icon: AppIcons.calendar,
                text: 'Date : ${formatDate(payment.createdAt)}'),
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

/// Formulaire « Nouveau paiement » : client → crédit à rembourser → montant.
/// Le serveur exige le crédit concerné, d'où le deuxième choix.
class _PaymentFormDialog extends StatefulWidget {
  final Snapshot data;
  final List<Credit> openCredits;

  const _PaymentFormDialog({required this.data, required this.openCredits});

  @override
  State<_PaymentFormDialog> createState() => _PaymentFormDialogState();
}

class _PaymentFormDialogState extends State<_PaymentFormDialog> {
  final _form = GlobalKey<FormState>();
  final _amount = TextEditingController();
  String? _customerId;
  String? _creditId;
  String _method = 'cash';
  bool _saving = false;

  /// Clients qui ont au moins un crédit ouvert.
  late final List<Customer> _customers = () {
    final ids = widget.openCredits.map((c) => c.customerId).toSet();
    return [
      for (final id in ids) widget.data.customerOf(id),
    ]..sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
  }();

  List<Credit> get _creditsOfCustomer => [
        for (final c in widget.openCredits)
          if (c.customerId == _customerId) c,
      ];

  Credit? get _selectedCredit {
    for (final c in widget.openCredits) {
      if (c.id == _creditId) return c;
    }
    return null;
  }

  @override
  void dispose() {
    _amount.dispose();
    super.dispose();
  }

  void _onCustomerChanged(String? id) {
    setState(() {
      _customerId = id;
      final credits = _creditsOfCustomer;
      // Un seul crédit ouvert : inutile de faire choisir.
      _creditId = credits.length == 1 ? credits.first.id : null;
    });
  }

  String? _validateAmount(String? text) {
    final amount = parseAmountInput(text ?? '');
    if (amount == null) return 'Entrez un montant supérieur à 0';
    final credit = _selectedCredit;
    if (credit != null && amount > widget.data.remaining(credit)) {
      return 'Maximum : ${formatCurrency(widget.data.remaining(credit))}';
    }
    return null;
  }

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await EcahierRepository.instance.createPayment(
        creditId: _creditId!,
        amount: parseAmountInput(_amount.text)!,
        method: _method,
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
      title: const Text('Nouveau paiement'),
      content: Form(
        key: _form,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<String>(
                initialValue: _customerId,
                isExpanded: true,
                decoration: modernInputDecoration('Client', icon: AppIcons.user),
                items: [
                  for (final c in _customers)
                    DropdownMenuItem(
                      value: c.id,
                      child: Text(c.name, overflow: TextOverflow.ellipsis),
                    ),
                ],
                onChanged: _onCustomerChanged,
                validator: (v) => v == null ? 'Choisissez un client' : null,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                key: ValueKey(_customerId),
                initialValue: _creditId,
                isExpanded: true,
                decoration:
                    modernInputDecoration('Crédit', icon: AppIcons.credits),
                items: [
                  for (final c in _creditsOfCustomer)
                    DropdownMenuItem(
                      value: c.id,
                      child: Text(
                        'Reste ${formatCurrency(widget.data.remaining(c))}'
                        '${c.dueDate != null ? ' · ${formatDate(c.dueDate!)}' : ''}',
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
                onChanged: (v) => setState(() => _creditId = v),
                validator: (v) => v == null ? 'Choisissez un crédit' : null,
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
                validator: _validateAmount,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _method,
                isExpanded: true,
                decoration: modernInputDecoration('Méthode'),
                items: [
                  for (final m in const [
                    'cash',
                    'mobile_money',
                    'bank_transfer',
                    'other'
                  ])
                    DropdownMenuItem(
                        value: m, child: Text(paymentMethodLabel(m))),
                ],
                onChanged: (v) => setState(() => _method = v ?? 'cash'),
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
