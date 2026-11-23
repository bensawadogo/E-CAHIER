import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'repositories/ecahier_repository.dart';
import 'screens/credits_screen.dart';
import 'screens/customers_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/payments_screen.dart';
import 'screens/sync_screen.dart';
import 'theme/app_icons.dart';
import 'theme/app_theme.dart';
import 'widgets/repo_builder.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
      systemNavigationBarColor: Colors.white,
      systemNavigationBarIconBrightness: Brightness.dark,
    ),
  );
  runApp(const EcahierApp());
}

class EcahierApp extends StatelessWidget {
  const EcahierApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Ecahier',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: const MainScreen(),
    );
  }
}

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> with WidgetsBindingObserver {
  /// Intervalle de réessai de l'envoi quand des éléments sont en attente
  /// (la connexion revient sans prévenir : pas de paquet de détection réseau
  /// pour rester léger).
  static const Duration _retryEvery = Duration(minutes: 2);

  final _repo = EcahierRepository.instance;
  int _selectedIndex = 0;
  Timer? _retryTimer;

  /// Onglets déjà ouverts : on ne construit un écran qu'à sa première visite,
  /// puis on le garde (position de liste conservée, pas de rechargement).
  final Set<int> _visited = {0};

  static const List<Widget> _screens = [
    DashboardScreen(),
    CustomersScreen(),
    CreditsScreen(),
    PaymentsScreen(),
    SyncScreen(),
  ];

  static const List<NavigationDestination> _destinations = [
    NavigationDestination(icon: Icon(AppIcons.dashboard), label: 'Accueil'),
    NavigationDestination(icon: Icon(AppIcons.customers), label: 'Clients'),
    NavigationDestination(icon: Icon(AppIcons.credits), label: 'Crédits'),
    NavigationDestination(icon: Icon(AppIcons.payments), label: 'Paiements'),
    NavigationDestination(icon: Icon(AppIcons.sync), label: 'Sync'),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_repo.sync());
    _retryTimer = Timer.periodic(_retryEvery, (_) async {
      if (await _repo.pendingCount() > 0) unawaited(_repo.sync(pull: false));
    });
  }

  @override
  void dispose() {
    _retryTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Retour sur l'app : on tente d'envoyer ce qui attend.
    if (state == AppLifecycleState.resumed) {
      unawaited(_repo.sync(pull: false));
    }
  }

  void _onItemTapped(int index) {
    setState(() {
      _selectedIndex = index;
      _visited.add(index);
    });
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _PendingBanner(onTap: () => _onItemTapped(4)),
            Expanded(
              child: IndexedStack(
                index: _selectedIndex,
                children: [
                  for (var i = 0; i < _screens.length; i++)
                    _visited.contains(i) ? _screens[i] : const SizedBox.shrink(),
                ],
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: _onItemTapped,
        height: 68,
        backgroundColor: colors.surfaceContainerLow,
        elevation: 0,
        shadowColor: colors.surfaceContainerHigh,
        indicatorColor: colors.primary.withValues(alpha: 0.12),
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        destinations: _destinations,
      ),
    );
  }
}

/// Bandeau discret « N éléments en attente d'envoi » : l'utilisateur sait que
/// ses données sont bien enregistrées sur le téléphone mais pas encore sur le
/// serveur. Disparaît quand tout est envoyé.
class _PendingBanner extends StatelessWidget {
  final VoidCallback onTap;

  const _PendingBanner({required this.onTap});

  @override
  Widget build(BuildContext context) {
    return RepoBuilder<int>(
      load: (repo) => repo.pendingCount(),
      loading: const SizedBox.shrink(),
      error: const SizedBox.shrink(),
      builder: (context, pending) {
        if (pending == 0) return const SizedBox.shrink();
        return Semantics(
          liveRegion: true,
          child: Material(
            color: AppColors.tertiary.withValues(alpha: 0.18),
            child: InkWell(
              onTap: onTap,
              child: Padding(
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                child: Row(
                  children: [
                    const Icon(AppIcons.cloudOff,
                        size: 18, color: AppColors.tertiaryText),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        pending == 1
                            ? '1 élément en attente d\'envoi'
                            : '$pending éléments en attente d\'envoi',
                        style: const TextStyle(
                            color: AppColors.onSurface,
                            fontWeight: FontWeight.w600),
                      ),
                    ),
                    const Text('Voir',
                        style: TextStyle(
                            color: AppColors.tertiaryText,
                            fontWeight: FontWeight.w700)),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
