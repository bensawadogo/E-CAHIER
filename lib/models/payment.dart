import '../utils/parsing.dart';

class Payment {
  final String id;
  final String customerId;

  /// Crédit remboursé par ce paiement (obligatoire côté serveur).
  final String creditId;

  /// Montant en FCFA.
  final int amount;
  final String method;
  final DateTime createdAt;

  const Payment({
    required this.id,
    required this.customerId,
    required this.creditId,
    required this.amount,
    this.method = 'cash',
    required this.createdAt,
  });

  factory Payment.fromJson(Map<String, dynamic> json) {
    return Payment(
      id: json['id'] as String? ?? '',
      customerId: json['customer_id'] as String? ?? '',
      creditId: json['credit_id'] as String? ?? '',
      amount: parseAmount(json['amount']),
      method: json['method'] as String? ?? 'cash',
      createdAt: parseServerDate(json['payment_date'] ?? json['created_at']),
    );
  }

  /// Corps de la requête de création (`POST /api/payments/`).
  Map<String, dynamic> toApiJson() => {
        'id': id,
        'customer_id': customerId,
        'credit_id': creditId,
        'amount': amount,
        'method': method,
      };
}
