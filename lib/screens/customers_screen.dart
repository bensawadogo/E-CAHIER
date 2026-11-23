import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../models/customer.dart';
import '../repositories/ecahier_repository.dart';
import '../theme/app_icons.dart';
import '../theme/app_theme.dart';
import '../utils/parsing.dart';
import '../widgets/ecahier_widgets.dart';
import '../widgets/repo_builder.dart';

class CustomersScreen extends StatefulWidget {
  const CustomersScreen({super.key});

  @override
  State<CustomersScreen> createState() => _CustomersScreenState();
}

class _CustomersScreenState extends State<CustomersScreen> {
  final _search = TextEditingController();

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  Future<void> _showAddDialog() async {
    final created = await showDialog<bool>(
      context: context,
      builder: (_) => const _CustomerFormDialog(),
    );
    if (created == true && mounted) showSnack(context, 'Client enregistré');
  }

  List<Customer> _filter(List<Customer> customers) {
    final query = _search.text.trim().toLowerCase();
    if (query.isEmpty) return customers;
    return customers
        .where((c) =>
            c.name.toLowerCase().contains(query) ||
            (c.phone ?? '').contains(query))
        .toList();
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
                const ScreenHeader(title: 'Clients'),
                const SizedBox(height: 16),
                TextField(
                  controller: _search,
                  decoration: modernInputDecoration('Rechercher un client',
                      icon: AppIcons.search),
                  onChanged: (_) => setState(() {}),
                ),
              ],
            ),
          ),
          Expanded(
            child: RepoBuilder<List<Customer>>(
              load: (repo) => repo.getCustomers(),
              builder: (context, customers) {
                if (customers.isEmpty) {
                  return const EmptyState(
                    icon: AppIcons.customers,
                    message: 'Aucun client.\nAppuyez sur + pour en ajouter.',
                  );
                }
                final filtered = _filter(customers);
                if (filtered.isEmpty) {
                  return const EmptyState(
                    icon: AppIcons.search,
                    message: 'Aucun client correspondant.',
                  );
                }
                return RefreshIndicator(
                  onRefresh: () => EcahierRepository.instance.sync(),
                  child: ListView.separated(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.fromLTRB(24, 8, 24, 96),
                    itemCount: filtered.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 8),
                    itemBuilder: (context, i) =>
                        _customerTile(context, filtered[i]),
                  ),
                );
              },
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        tooltip: 'Nouveau client',
        onPressed: _showAddDialog,
        child: const Icon(AppIcons.add),
      ),
    );
  }

  Widget _customerTile(BuildContext context, Customer customer) {
    final colors = Theme.of(context).colorScheme;
    return Card(
      child: ListTile(
        leading: CustomerAvatar(name: customer.name),
        title: Text(customer.name,
            style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(
          (customer.phone ?? '').isEmpty ? '—' : customer.phone!,
          style: TextStyle(color: colors.onSurfaceVariant),
        ),
        trailing: customer.isActive
            ? null
            : Icon(AppIcons.pause, size: 16, color: colors.onSurfaceVariant),
        onTap: () => _showCustomerDetail(context, customer),
      ),
    );
  }

  void _showCustomerDetail(BuildContext context, Customer customer) {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(AppColors.borderRadius)),
        title: Row(
          children: [
            CustomerAvatar(name: customer.name, radius: 20),
            const SizedBox(width: 12),
            Expanded(child: Text(customer.name)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if ((customer.phone ?? '').isNotEmpty)
              InfoRow(icon: AppIcons.phone, text: customer.phone!),
            if ((customer.address ?? '').isNotEmpty)
              InfoRow(icon: AppIcons.place, text: customer.address!),
            if ((customer.notes ?? '').isNotEmpty)
              InfoRow(icon: AppIcons.note, text: customer.notes!),
            InfoRow(
                icon: AppIcons.calendar,
                text: 'Ajouté le ${formatDate(customer.createdAt)}'),
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

/// Formulaire « Nouveau client ».
class _CustomerFormDialog extends StatefulWidget {
  const _CustomerFormDialog();

  @override
  State<_CustomerFormDialog> createState() => _CustomerFormDialogState();
}

class _CustomerFormDialogState extends State<_CustomerFormDialog> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _address = TextEditingController();
  final _notes = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    _address.dispose();
    _notes.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_saving || !_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await EcahierRepository.instance.createCustomer(
        name: _name.text,
        phone: _phone.text,
        address: _address.text,
        notes: _notes.text,
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
      title: const Text('Nouveau client'),
      content: Form(
        key: _form,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: _name,
                autofocus: true,
                decoration: modernInputDecoration('Nom', icon: AppIcons.user),
                textInputAction: TextInputAction.next,
                textCapitalization: TextCapitalization.words,
                inputFormatters: [LengthLimitingTextInputFormatter(200)],
                validator: (v) => (v ?? '').trim().isEmpty
                    ? 'Entrez le nom du client'
                    : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _phone,
                decoration:
                    modernInputDecoration('Téléphone', icon: AppIcons.phone),
                keyboardType: TextInputType.phone,
                textInputAction: TextInputAction.next,
                inputFormatters: [LengthLimitingTextInputFormatter(20)],
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _address,
                decoration:
                    modernInputDecoration('Adresse', icon: AppIcons.place),
                textInputAction: TextInputAction.next,
                inputFormatters: [LengthLimitingTextInputFormatter(500)],
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _notes,
                decoration: modernInputDecoration('Notes'),
                maxLines: 3,
                inputFormatters: [LengthLimitingTextInputFormatter(1000)],
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
