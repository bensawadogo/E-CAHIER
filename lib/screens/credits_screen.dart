import 'package:flutter/material.dart';
import '../repositories/ecahier_repository.dart';
import '../models/index.dart';
import '../widgets/ecahier_widgets.dart';
import '../theme/app_theme.dart';
import '../theme/app_icons.dart';

class CreditsScreen extends StatefulWidget {
  const CreditsScreen({super.key});

  @override
  State<CreditsScreen> createState() => _CreditsScreenState();
}

class _CreditsScreenState extends State<CreditsScreen> {
  final _repository = EcahierRepository();
  late Future<List<Credit>> _futureCredits;
  late Future<List<Customer>> _futureCustomers;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  void _loadData() {
    _futureCredits = _repository.getCredits();
    _futureCustomers = _repository.getCustomers();
  }

  void _showAddDialog() {
    String? customerId;
    final amountController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppColors.borderRadius)),
        title: const Text('Nouveau crédit'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            FutureBuilder<List<Customer>>(
              future: _futureCustomers,
               builder: (context, snap) {
                if (snap.hasError) {
                  return const Text(
                    'Impossible de charger les clients',
                    style: TextStyle(color: Colors.red),
                  );
                }
                final customers = snap.data ?? [];
                return DropdownButtonFormField<String>(
                  value: customerId,
                  isExpanded: true,
                  decoration: InputDecoration(
                    labelText: 'Client',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(AppColors.buttonRadius),
                      borderSide: BorderSide.none,
                    ),
                    filled: true,
                  ),
                  items: customers
                      .map((c) => DropdownMenuItem(
                          value: c.id,
                          child: Text(c.name,
                              overflow: TextOverflow.ellipsis)))
                      .toList(),
                  onChanged: (v) => customerId = v,
                );
              }),
            const SizedBox(height: 12),
            TextField(
              controller: amountController,
              decoration: modernInputDecoration('Montant', icon: AppIcons.money),
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
          FilledButton(
            onPressed: () async {
              if (customerId == null || amountController.text.isEmpty) return;
              final cents =
                  (double.parse(amountController.text) * 100).round();
              await _repository.createCredit(Credit(
                id: DateTime.now().millisecondsSinceEpoch.toString(),
                customerId: customerId!,
                amountCentimes: cents,
                createdAt: DateTime.now(),
              ));
              if (!mounted) return;
              Navigator.pop(context);
              setState(() => _loadData());
            },
            child: const Text('Enregistrer'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Crédits',
                  style: Theme.of(context)
                      .textTheme
                      .headlineLarge
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 16),
                FutureBuilder<List<List<Object>>>(
                  future: Future.wait([_futureCredits, _futureCustomers]),
                  builder: (context, snapshot) {
                    if (snapshot.hasError) {
                      return ErrorState(
                        message: 'Erreur de chargement',
                        onRetry: () => setState(() => _loadData()),
                      );
                    }
                    if (snapshot.connectionState == ConnectionState.waiting) {
                      return const Center(child: CircularProgressIndicator());
                    }
                    final credits = (snapshot.data?[0] ?? <Credit>[]).cast<Credit>();
                    final totalActive = credits
                        .where((c) => c.status != 'paid')
                        .fold<int>(0, (s, c) => s + c.amountCentimes);
                    return Text(
                      'Total à rembourser : ${formatCurrency(totalActive)}',
                      style: Theme.of(context)
                          .textTheme
                          .titleMedium
                          ?.copyWith(fontWeight: FontWeight.w600),
                    );
                  },
                ),
              ],
            ),
          ),
          Expanded(
            child: FutureBuilder<List<List<Object>>>(
              future: Future.wait([_futureCredits, _futureCustomers]),
              builder: (context, snapshot) {
                if (snapshot.hasError) {
                  return ErrorState(
                    message: 'Erreur de chargement',
                    onRetry: () => setState(() => _loadData()),
                  );
                }
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                final credits = (snapshot.data?[0] ?? <Credit>[]).cast<Credit>();
                final customers = (snapshot.data?[1] ?? <Customer>[]).cast<Customer>();
                final customerMap = {for (final c in customers) c.id: c};
                if (credits.isEmpty) {
                  return const EmptyState(
                    icon: AppIcons.credits,
                    message: 'Aucun crédit enregistré.',
                  );
                }
                return ListView.separated(
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
                  itemCount: credits.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, i) {
                    final credit = credits[i];
                    final customer = customerMap[credit.customerId] ??
                        Customer(
                            id: '', name: 'Inconnu', createdAt: DateTime.now()));
                    return _creditTile(context, credit, customer);
                  },
                );
              },
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddDialog,
        child: const Icon(AppIcons.add),
      ),
    );
  }


  Widget _creditTile(BuildContext context, Credit credit, Customer customer) {
    final colors = Theme.of(context).colorScheme;
    final isPaid = credit.status == 'paid';
    final isOverdue = credit.status == 'active' &&
        credit.dueDate != null &&
        credit.dueDate!.isBefore(DateTime.now());
    final Color accent = isPaid
        ? colors.primary
        : (isOverdue ? colors.error : AppColors.tertiary);
    final String statusLabel = isPaid
        ? 'Payé'
        : (isOverdue ? 'En retard' : 'Actif');

    return Card(
      child: ListTile(
        leading: CircleAvatar(
          radius: 22,
          backgroundColor: avatarColor(customer.name),
          child: Text(nameInitials(customer.name),
              style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                  fontSize: 16)),
        ),
        title: Text(customer.name,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(formatCurrency(credit.amountCentimes),
            style: TextStyle(
                color: accent, fontWeight: FontWeight.w600)),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            StatusBadge(label: statusLabel, color: accent),
            const SizedBox(height: 4),
            if (credit.dueDate != null)
              Text(
                credit.dueDate!.toLocal().toString().split(' ')[0],
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: colors.onSurfaceVariant,
                    ),
              ),
          ],
        ),
        onTap: () => _showCreditDetail(context, credit, customer),
      ),
    );
  }

  void _showCreditDetail(
      BuildContext context, Credit credit, Customer customer) {
    showDialog(
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
            _infoRow(AppIcons.money,
                'Montant: ${formatCurrency(credit.amountCentimes)}'),
            if (credit.dueDate != null)
              _infoRow(AppIcons.calendar,
                  'Échéance: ${credit.dueDate!.toLocal().toString().split(' ')[0]}'),
            _infoRow(AppIcons.info,
                'Statut: ${creditStatusLabel(credit.status)}'),
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

  Widget _infoRow(IconData icon, String text) {
    final colors = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 18, color: colors.onSurfaceVariant),
          const SizedBox(width: 10),
          Expanded(
              child: Text(text,
                  style: TextStyle(color: colors.onSurfaceVariant))),
        ],
      ),
    );
  }
}

