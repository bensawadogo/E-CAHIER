import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../models/index.dart';
import '../widgets/ecahier_widgets.dart';

class PaymentsScreen extends StatefulWidget {
  const PaymentsScreen({super.key});

  @override
  State<PaymentsScreen> createState() => _PaymentsScreenState();
}

class _PaymentsScreenState extends State<PaymentsScreen> {
  late Future<List<Payment>> _futurePayments;
  late Future<List<Customer>> _futureCustomers;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  void _loadData() {
    _futurePayments = ApiService().getPayments();
    _futureCustomers = ApiService().getCustomers();
  }

  void _showAddDialog() {
    String? customerId;
    final amountController = TextEditingController();
    String method = 'cash';

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16)),
        title: const Text('Nouveau paiement'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            FutureBuilder<List<Customer>>(
              future: _futureCustomers,
              builder: (context, snap) {
                final customers = snap.data ?? [];
                return DropdownButtonFormField<String>(
                  value: customerId,
                  isExpanded: true,
                  decoration: InputDecoration(
                    labelText: 'Client',
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(14),
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
              decoration: InputDecoration(
                labelText: 'Montant',
                prefixIcon: const Icon(Icons.money),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide: BorderSide.none,
                ),
                filled: true,
              ),
              keyboardType:
                  const TextInputType.numberWithOptions(decimal: true),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: method,
              decoration: InputDecoration(
                labelText: 'Méthode',
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(14),
                  borderSide: BorderSide.none,
                ),
                filled: true,
              ),
              items: ['cash', 'mobile_money', 'bank_transfer', 'other']
                  .map((m) => DropdownMenuItem(
                      value: m, child: Text(paymentMethodLabel(m))))
                  .toList(),
              onChanged: (v) => method = v ?? 'cash',
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
          FilledButton(
            onPressed: () async {
              if (customerId == null || amountController.text.isEmpty) return;
              await ApiService().createPayment(Payment(
                id: DateTime.now().millisecondsSinceEpoch.toString(),
                customerId: customerId!,
                amount: double.parse(amountController.text),
                method: method,
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
                  'Paiements',
                  style: Theme.of(context)
                      .textTheme
                      .headlineLarge
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 16),
                FutureBuilder(
                  future: Future.wait([_futurePayments, _futureCustomers]),
                  builder: (context, snapshot) {
                    if (snapshot.connectionState ==
                        ConnectionState.waiting) {
                      return const Center(
                          child: CircularProgressIndicator());
                    }
                    final payments = snapshot.data?[0] ?? [];
                    final total = payments
                        .fold<double>(0, (s, p) => s + p.amount);
                    return Text(
                      'Total perçu : ${formatCurrency(total)}',
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
            child: FutureBuilder(
              future: Future.wait([_futurePayments, _futureCustomers]),
              builder: (context, snapshot) {
                if (snapshot.connectionState ==
                    ConnectionState.waiting) {
                  return const Center(
                      child: CircularProgressIndicator());
                }
                final payments = snapshot.data?[0] ?? [];
                final customers = snapshot.data?[1] ?? [];
                if (payments.isEmpty) {
                  return const EmptyState(
                    icon: Icons.payments,
                    message: 'Aucun paiement enregistré.',
                  );
                }
                return ListView.separated(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 24, vertical: 8),
                  itemCount: payments.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, i) {
                    final payment = payments[i];
                    final customer = customers.firstWhere(
                        (c) => c.id == payment.customerId,
                        orElse: () => Customer(
                            id: '',
                            name: 'Inconnu',
                            createdAt: DateTime.now()));
                    return _paymentTile(context, payment, customer);
                  },
                );
              },
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddDialog,
        child: const Icon(Icons.add),
      ),
    );
  }

  Widget _paymentTile(
      BuildContext context, Payment payment, Customer customer) {
    final colors = Theme.of(context).colorScheme;
    final icon = paymentMethodIcon(payment.method);

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
        subtitle: Row(
          children: [
            Icon(icon, size: 16, color: colors.onSurfaceVariant),
            const SizedBox(width: 4),
            Text(paymentMethodLabel(payment.method),
                style: TextStyle(color: colors.onSurfaceVariant)),
          ],
        ),
        trailing: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(formatCurrency(payment.amount),
                style: TextStyle(
                    color: colors.tertiary,
                    fontWeight: FontWeight.w700)),
            Text(
              payment.createdAt.toLocal().toString().split(' ')[0],
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: colors.onSurfaceVariant,
                  ),
            ),
          ],
        ),
        onTap: () => _showPaymentDetail(context, payment, customer),
      ),
    );
  }

  void _showPaymentDetail(
      BuildContext context, Payment payment, Customer customer) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16)),
        title: Text(customer.name,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _infoRow(Icons.money,
                'Montant: +${formatCurrency(payment.amount)}'),
            _infoRow(Icons.payment,
                'Méthode: ${paymentMethodLabel(payment.method)}'),
            _infoRow(Icons.calendar_today,
                'Date: ${payment.createdAt.toLocal().toString().split(' ')[0]}'),
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
      child: Row(children: [
        Icon(icon, size: 18, color: colors.onSurfaceVariant),
        const SizedBox(width: 10),
        Expanded(child: Text(text,
            style: TextStyle(color: colors.onSurfaceVariant))),
      ]),
    );
  }
}
