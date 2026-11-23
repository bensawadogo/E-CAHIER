import '../utils/parsing.dart';

class Customer {
  final String id;
  final String name;
  final String? phone;
  final String? address;
  final String? notes;
  final bool isActive;
  final DateTime createdAt;

  /// Totaux en FCFA, calculés par le serveur.
  final int totalCredit;
  final int totalPaid;

  const Customer({
    required this.id,
    required this.name,
    this.phone,
    this.address,
    this.notes,
    this.isActive = true,
    required this.createdAt,
    this.totalCredit = 0,
    this.totalPaid = 0,
  });

  /// Client affiché quand l'original est introuvable (ex. pas encore reçu).
  factory Customer.unknown() =>
      Customer(id: '', name: 'Inconnu', createdAt: DateTime.now().toUtc());

  factory Customer.fromJson(Map<String, dynamic> json) {
    return Customer(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? '',
      phone: json['phone'] as String?,
      address: json['address'] as String?,
      notes: json['notes'] as String?,
      isActive: json['is_active'] as bool? ?? true,
      createdAt: parseServerDate(json['created_at']),
      totalCredit: parseAmount(json['total_credit']),
      totalPaid: parseAmount(json['total_paid']),
    );
  }

  /// Corps de la requête de création (`POST /api/customers/`).
  Map<String, dynamic> toApiJson() => {
        'id': id,
        'name': name,
        'phone': phone ?? '',
        'address': address ?? '',
        'notes': notes ?? '',
      };
}
