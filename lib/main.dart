import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/dashboard_screen.dart';
import 'screens/customers_screen.dart';
import 'screens/credits_screen.dart';
import 'screens/payments_screen.dart';
import 'screens/sync_screen.dart';
import 'theme/app_icons.dart';
import 'theme/app_theme.dart';

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

class _MainScreenState extends State<MainScreen> {
  int _selectedIndex = 0;

  static const List<Widget> _screens = [
    DashboardScreen(),
    CustomersScreen(),
    CreditsScreen(),
    PaymentsScreen(),
    SyncScreen(),
  ];

  static const List<NavigationDestination> _destinations = [
    NavigationDestination(
      icon: Icon(AppIcons.dashboard),
      label: 'Tableau de bord',
    ),
    NavigationDestination(
      icon: Icon(AppIcons.customers),
      label: 'Clients',
    ),
    NavigationDestination(
      icon: Icon(AppIcons.credits),
      label: 'Crédits',
    ),
    NavigationDestination(
      icon: Icon(AppIcons.payments),
      label: 'Paiements',
    ),
    NavigationDestination(
      icon: Icon(AppIcons.sync),
      label: 'Sync',
    ),
  ];

  void _onItemTapped(int index) {
    setState(() => _selectedIndex = index);
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Scaffold(
      body: SafeArea(child: _screens[_selectedIndex]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _selectedIndex,
        onDestinationSelected: _onItemTapped,
        height: 64,
        backgroundColor: colors.surfaceContainerLow,
        elevation: 0,
        shadowColor: colors.surfaceContainerHigh,
        indicatorColor: colors.primary.withOpacity(0.12),
        labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
        destinations: _destinations,
      ),
    );
  }
}
