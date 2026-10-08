import 'package:flutter/material.dart';

import '../repositories/ecahier_repository.dart';

import '../models/index.dart';

import '../widgets/ecahier_widgets.dart';
import '../theme/app_icons.dart';
import '../theme/app_theme.dart';
import '../theme/app_icons.dart';



class DashboardScreen extends StatefulWidget {

  const DashboardScreen({super.key});



  @override

  State<DashboardScreen> createState() => _DashboardScreenState();

}



class _DashboardScreenState extends State<DashboardScreen> {

  final _repository = EcahierRepository();

  late Future<List<Customer>> _futureCustomers;

  late Future<List<Credit>> _futureCredits;

  late Future<List<Payment>> _futurePayments;



  @override

  void initState() {

    super.initState();

    _loadData();

  }



  void _loadData() {

    _futureCustomers = _repository.getCustomers();

    _futureCredits = _repository.getCredits();

    _futurePayments = _repository.getPayments();

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

            FutureBuilder<List<List<Object>>>(

              future: Future.wait([
                _futureCustomers,

                _futureCredits,

                _futurePayments

              ]),

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

                final customers = (snapshot.data?[0] ?? <Customer>[]).cast<Customer>();

                final credits = (snapshot.data?[1] ?? <Credit>[]).cast<Credit>();

                final payments = (snapshot.data?[2] ?? <Payment>[]).cast<Payment>();

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

                      icon: AppIcons.user,

                      color: colors.primary,

                    ),

                    StatCard(

                      title: 'Crédits',

                      value: '${credits.length}',

                      icon: AppIcons.credits,

                      color: AppColors.tertiary,

                    ),

                    StatCard(

                      title: 'Paiements',

                      value: '${payments.length}',

                      icon: AppIcons.payments,

                      color: colors.secondary,

                    ),

                    StatCard(

                      title: 'Alertes',

                      value: '$overdue',

                      icon: AppIcons.warning,

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

                title: 'Derniers clients', icon: AppIcons.user),

            FutureBuilder<List<Customer>>(

              future: _futureCustomers,

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

                final customers = snapshot.data ?? [];

                final recent = customers.reversed.take(5).toList();



                if (recent.isEmpty) {

                  return const EmptyState(

                    icon: AppIcons.user,

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

                icon: AppIcons.warning),

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

                final customers = (snapshot.data?[1] ?? <Customer>[]).cast<Customer>();

                final customerMap = {for (final c in customers) c.id: c};

                final now = DateTime.now();

                final overdueCredits = credits

                    .where((c) =>

                        c.status == 'active' &&

                        c.dueDate != null &&

                        c.dueDate!.isBefore(now))

                    .toList();



                if (overdueCredits.isEmpty) {

                  return const EmptyState(

                    icon: AppIcons.checkCircle,

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

                      final customer = customerMap[credit.customerId] ??
                          Customer(
                              id: '',
                              name: 'Inconnu',
                              createdAt: DateTime.now());

                      return ListTile(

                        leading: CircleAvatar(

                          backgroundColor:

                              colors.error.withOpacity(0.12),

                          child: const Icon(AppIcons.credits,

                              color: AppColors.error),

                        ),

                        title: Text(customer.name,

                            style:

                                const TextStyle(color: AppColors.error)),

                        subtitle: Text(formatCurrency(credit.amountCentimes),

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

