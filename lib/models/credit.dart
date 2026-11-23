import '../utils/parsing.dart';

/// Statuts d'un crédit (mêmes valeurs que le serveur).
class CreditStatus {
  static const pending = 'pending';
  static const partial = 'partial';
  static const paid = 'paid';
  static const cancelled = 'cancelled';
}

class Credit {
  final String id;
  final String customerId;

  /// Montant en FCFA (le FCFA n'a pas de centimes).
  final int amount;
  final String description;
  final String status;
  final DateTime? dueDate;
  final DateTime createdAt;

  const Credit({
    required this.id,
    required this.customerId,
    required this.amount,
    this.description = '',
    this.status = CreditStatus.pending,
    this.dueDate,
    required this.createdAt,
  });

  /// Reste à rembourser (ni payé, ni annulé).
  bool get isOpen =>
      status == CreditStatus.pending || status == CreditStatus.partial;

  bool isOverdue([DateTime? now]) =>
      isOpen &&
      dueDate != null &&
      dueDate!.isBefore(now ?? DateTime.now().toUtc());

  factory Credit.fromJson(Map<String, dynamic> json) {
    return Credit(
      id: json['id'] as String? ?? '',
      customerId: json['customer_id'] as String? ?? '',
      amount: parseAmount(json['amount']),
      description: json['description'] as String? ?? '',
      status: json['status'] as String? ?? CreditStatus.pending,
      dueDate:
          json['due_date'] != null ? parseServerDate(json['due_date']) : null,
      createdAt: parseServerDate(json['created_at']),
    );
  }

  /// Corps de la requête de création (`POST /api/credits/`).
  Map<String, dynamic> toApiJson() => {
        'id': id,
        'customer_id': customerId,
        'amount': amount,
        'description': description,
        'due_date': dueDate?.toUtc().toIso8601String(),
      };
}
