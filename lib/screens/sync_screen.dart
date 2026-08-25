import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../models/index.dart';
import '../widgets/ecahier_widgets.dart';
import '../theme/app_theme.dart';

class SyncScreen extends StatefulWidget {
  const SyncScreen({super.key});

  @override
  State<SyncScreen> createState() => _SyncScreenState();
}

class _SyncScreenState extends State<SyncScreen> {
  late Future<List<Customer>> _futureCustomers;
  late Future<List<Credit>> _futureCredits;
  late Future<List<Payment>> _futurePayments;
  bool _isSyncing = false;

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

  void _syncNow() async {
    setState(() => _isSyncing = true);
    await Future.delayed(const Duration(milliseconds: 800));
    setState(() => _isSyncing = false);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Synchronisation terminée')),
    );
    setState(() => _loadData());
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () async {
          setState(() => _loadData());
        },
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Synchronisation',
                style: Theme.of(context)
                    .textTheme
                    .headlineLarge
                    ?.copyWith(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 4),
              Text(
                'Synchronisez vos données en ligne ou hors ligne',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: colors.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 24),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Statut',
                        style: Theme.of(context)
                            .textTheme
                            .titleLarge
                            ?.copyWith(
                              color: colors.primary,
                              fontWeight: FontWeight.w600,
                            ),
                      ),
                      const SizedBox(height: 16),
                      FutureBuilder(
                        future: Future.wait([
                          _futureCustomers,
                          _futureCredits,
                          _futurePayments
                        ]),
                        builder: (context, snapshot) {
                          if (snapshot.connectionState ==
                              ConnectionState.waiting) {
                            return const Center(
                                child: CircularProgressIndicator());
                          }
                          final customers = snapshot.data?[0] ?? [];
                          final credits = snapshot.data?[1] ?? [];
                          final payments = snapshot.data?[2] ?? [];
                          return Column(
                            children: [
                              _buildStatRow(context, 'Clients',
                                  customers.length, colors.primary),
                              const SizedBox(height: 10),
                              _buildStatRow(context, 'Crédits',
                                  credits.length, AppColors.tertiary),
                              const SizedBox(height: 10),
                              _buildStatRow(context, 'Paiements',
                                  payments.length, colors.secondary),
                            ],
                          );
                        },
                      ),
                    ],
                  ),
              ),
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: _isSyncing
                    ? FilledButton.icon(
                        onPressed: null,
                        icon: const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            color: Colors.white,
                            strokeWidth: 2,
                          ),
                        ),
                        label: const Text('Synchronisation...'),
                      )
                    : FilledButton.icon(
                        onPressed: _syncNow,
                        icon: const Icon(Icons.sync_outlined),
                        label: const Text('Synchroniser maintenant'),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatRow(
      BuildContext context, String label, int count, Color color) {
    final colors = Theme.of(context).colorScheme;
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: colors.onSurfaceVariant,
                )),
        Text('$count éléments',
            style: TextStyle(
                color: color, fontWeight: FontWeight.w700)),
      ],
    );
  }
}

