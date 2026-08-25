import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../models/index.dart';
import '../widgets/ecahier_widgets.dart';
import '../theme/app_theme.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late Future<List<Customer>> _futureCustomers;
  late Future<List<Credit>> _futureCredits;
  late Future<List<Payment>> _futurePayments;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  void _loadData() {
    final api = ApiService();
    _futureCustomers = api.getCustomers();
    _futureCredits = api.getCredits();
    _futurePayments = api.getPayments();
  }

  int _overdueCount(List<Credit> credits) {
    final now = DateTime.now();
    return credits
        .where((c) =>
            c.status == 'active' &&
            c.dueDate != null &&
            c.dueDate!.isBefore(now))
        .length;
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return RefreshIndicator(
      onRefresh: () async => setState(() => _loadData()),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Tableau de bord',
              style: Theme.of(context)
                  .textTheme
                  .headlineLarge
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(
              'Suivi de votre caisse en temps réel',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: colors.onSurfaceVariant,
                  ),
            ),
            const SizedBox(height: 24),

            FutureBuilder(
              future: Future.wait([
                _futureCustomers,
                _futureCredits,
                _futurePayments
              ]),
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                final customers = snapshot.data?[0] ?? [];
                final credits = snapshot.data?[1] ?? [];
                final payments = snapshot.data?[2] ?? [];
                final overdue = _overdueCount(credits);

                return GridView.count(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisCount: 2,
                  mainAxisSpacing: 12,
                  crossAxisSpacing: 12,
                  childAspectRatio: 1.6,
                  children: [
                    StatCard(
                      title: 'Clients',
                      value: '${customers.length}',
                      icon: Icons.person,
                      color: colors.primary,
                    ),
                    StatCard(
                      title: 'Crédits',
                      value: '${credits.length}',
                      icon: Icons.credit_card,
                      color: AppColors.tertiary,
                    ),
                    StatCard(
                      title: 'Paiements',
                      value: '${payments.length}',
                      icon: Icons.payments,
                      color: colors.secondary,
                    ),
                    StatCard(
                      title: 'Alertes',
                      value: '$overdue',
                      icon: Icons.warning,
                      color: colors.error,
                      backgroundColor:
                          colors.errorContainer.withOpacity(0.3),
                    ),
                  ],
                );
              },
            ),

            const SizedBox(height: 24),

            SectionHeader(
                title: 'Derniers clients', icon: Icons.person),
            FutureBuilder<List<Customer>>(
              future: _futureCustomers,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                final customers = snapshot.data ?? [];
                final recent = customers.reversed.take(5).toList();

                if (recent.isEmpty) {
                  return const EmptyState(
                    icon: Icons.person_outline,
                    message: 'Aucun client enregistré.',
                  );
                }

                return Card(
                  child: ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: recent.length,
                    separatorBuilder: (_, __) =>
                        const Divider(height: 1, indent: 56),
                    itemBuilder: (context, index) {
                      final c = recent[index];
                      return ListTile(
                        leading: CircleAvatar(
                          backgroundColor: avatarColor(c.name),
                          child: Text(
                            nameInitials(c.name),
                            style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.bold),
                          ),
                        ),
                        title: Text(c.name),
                        subtitle: Text(c.phone ?? ''),
                        trailing: Text(
                          c.createdAt
                              .toLocal()
                              .toString()
                              .split(' ')[0],
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(color: colors.onSurfaceVariant),
                        ),
                      );
                    },
                  ),
                );
              },
            ),

            SectionHeader(
                title: 'Crédits en retard',
                icon: Icons.warning_amber_outlined),
            FutureBuilder(
              future: Future.wait([_futureCredits, _futureCustomers]),
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                final credits = snapshot.data?[0] ?? [];
                final customers = snapshot.data?[1] ?? [];
                final now = DateTime.now();
                final overdueCredits = credits
                    .where((c) =>
                        c.status == 'active' &&
                        c.dueDate != null &&
                        c.dueDate!.isBefore(now))
                    .toList();

                if (overdueCredits.isEmpty) {
                  return const EmptyState(
                    icon: Icons.check_circle_outline,
                    message: 'Aucun crédit en retard.',
                  );
                }

                return Card(
                  child: ListView.separated(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    itemCount: overdueCredits.length,
                    separatorBuilder: (_, __) =>
                        const Divider(height: 1, indent: 56),
                    itemBuilder: (context, index) {
                      final credit = overdueCredits[index];
                      final customer = customers.firstWhere(
                        (c) => c.id == credit.customerId,
                        orElse: () => Customer(
                            id: '',
                            name: 'Inconnu',
                            createdAt: DateTime.now()),
                      );
                      return ListTile(
                        leading: CircleAvatar(
                          backgroundColor:
                              colors.error.withOpacity(0.12),
                          child: const Icon(Icons.credit_card,
                              color: AppColors.error),
                        ),
                        title: Text(customer.name,
                            style:
                                const TextStyle(color: AppColors.error)),
                        subtitle: Text(formatCurrency(credit.amount),
                            style: const TextStyle(
                                color: AppColors.error,
                                fontWeight: FontWeight.w600)),
                        trailing: credit.dueDate != null
                            ? Text(
                                credit.dueDate!
                                    .toLocal()
                                    .toString()
                                    .split(' ')[0],
                                style: Theme.of(context)
                                    .textTheme
                                    .bodySmall
                                    ?.copyWith(
                                        color: colors.onSurfaceVariant),
                              )
                            : null,
                      );
                    },
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
