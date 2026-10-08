class Payment {
  final String id;
  final String customerId;
  final int amountCentimes;
  final String method;
  final DateTime createdAt;

  Payment({
    required this.id,
    required this.customerId,
    required this.amountCentimes,
    this.method = 'cash',
    required this.createdAt,
  });

  factory Payment.fromJson(Map<String, dynamic> json) {
    return Payment(
      id: json['id'] ?? '',
      customerId: json['customer_id'] ?? '',
      amountCentimes: ((json['amount'] ?? 0) as num).toInt(),
      method: json['method'] ?? 'cash',
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'customer_id': customerId,
      'amount': amountCentimes,
      'method': method,
      'created_at': createdAt.toIso8601String(),
    };
  }
}
