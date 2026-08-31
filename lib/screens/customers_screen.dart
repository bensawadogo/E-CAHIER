import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../models/index.dart';
import '../widgets/ecahier_widgets.dart';
import '../theme/app_theme.dart';
import '../theme/app_icons.dart';

class CustomersScreen extends StatefulWidget {
  const CustomersScreen({super.key});

  @override
  State<CustomersScreen> createState() => _CustomersScreenState();
}

class _CustomersScreenState extends State<CustomersScreen> {
  late Future<List<Customer>> _futureCustomers;
  final _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadCustomers();
  }

  void _loadCustomers() {
    _futureCustomers = ApiService().getCustomers();
  }

  void _showAddDialog() {
    final _nameController = TextEditingController();
    final _phoneController = TextEditingController();
    final _addressController = TextEditingController();
    final _notesController = TextEditingController();

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppColors.borderRadius)),
        title: const Text('Nouveau client'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: _nameController,
                decoration: modernInputDecoration('Nom', icon: AppIcons.user),
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _phoneController,
                decoration: modernInputDecoration('Téléphone', icon: AppIcons.phone),
                keyboardType: TextInputType.phone,
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _addressController,
                decoration: modernInputDecoration('Adresse', icon: AppIcons.place),
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _notesController,
                decoration: modernInputDecoration('Notes'),
                maxLines: 3,
              ),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Annuler')),
          FilledButton(
            onPressed: () async {
              if (_nameController.text.trim().isEmpty) return;
              final customer = Customer(
                id: DateTime.now().millisecondsSinceEpoch.toString(),
                name: _nameController.text,
                phone: _phoneController.text,
                address: _addressController.text,
                notes: _notesController.text,
                createdAt: DateTime.now(),
              );
              await ApiService().createCustomer(customer);
              if (!mounted) return;
              Navigator.pop(context);
              setState(() => _loadCustomers());
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
                  'Clients',
                  style: Theme.of(context)
                      .textTheme
                      .headlineLarge
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'Rechercher un client...',
                    prefixIcon: const Icon(AppIcons.search),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(AppColors.buttonRadius),
                      borderSide: BorderSide.none,
                    ),
                    filled: true,
                    fillColor: Theme.of(context).colorScheme.surfaceContainer,
                  ),
                  onChanged: (value) => setState(() {}),
                ),
              ],
            ),
          ),
          Expanded(
            child: FutureBuilder<List<Customer>>(
              future: _futureCustomers,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                final customers = snapshot.data ?? [];
                final filtered = customers
                    .where((c) => c.name
                        .toLowerCase()
                        .contains(_searchController.text.toLowerCase()))
                    .toList();
                if (filtered.isEmpty) {
                  return const EmptyState(
                    icon: AppIcons.search,
                    message: 'Aucun client correspondant.',
                  );
                }
                return ListView.separated(
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
                  itemCount: filtered.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (context, index) {
                    final c = filtered[index];
                    return _customerTile(context, c);
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

  Widget _customerTile(BuildContext context, Customer customer) {
    final colors = Theme.of(context).colorScheme;
    return Card(
      child: ListTile(
        leading: CircleAvatar(
          radius: 22,
          backgroundColor: avatarColor(customer.name),
          child: Text(
            nameInitials(customer.name),
            style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 16),
          ),
        ),
        title: Text(customer.name,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(customer.phone ?? '—',
            style: TextStyle(color: colors.onSurfaceVariant)),
        trailing: customer.isActive == false
            ? const Icon(AppIcons.pause, size: 16, color: Colors.grey)
            : null,
        onTap: () => _showCustomerDetail(context, customer),
      ),
    );
  }

  void _showCustomerDetail(BuildContext context, Customer customer) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppColors.borderRadius)),
        title: Row(
          children: [
            CircleAvatar(
              backgroundColor: avatarColor(customer.name),
              child: Text(nameInitials(customer.name),
                  style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold)),
            ),
            const SizedBox(width: 12),
            Expanded(child: Text(customer.name)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (customer.phone != null && customer.phone!.isNotEmpty)
              _infoRow(AppIcons.phone, customer.phone!),
            if (customer.address != null && customer.address!.isNotEmpty)
              _infoRow(AppIcons.place, customer.address!),
            _infoRow(AppIcons.calendar,
                customer.createdAt.toLocal().toString().split(' ')[0]),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Fermer')),
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
          Expanded(child: Text(text, style: TextStyle(color: colors.onSurfaceVariant))),
        ],
      ),
    );
  }
}

