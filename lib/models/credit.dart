class Credit {
  final String id;
  final String customerId;
  final int amountCentimes;
  final String status;
  final DateTime? dueDate;
  final DateTime createdAt;

  Credit({
    required this.id,
    required this.customerId,
    required this.amountCentimes,
    this.status = 'active',
    this.dueDate,
    required this.createdAt,
  });

  factory Credit.fromJson(Map<String, dynamic> json) {
    return Credit(
      id: json['id'] ?? '',
      customerId: json['customer_id'] ?? '',
      amountCentimes: ((json['amount'] ?? 0) as num).toInt(),
      status: json['status'] ?? 'active',
      dueDate: json['due_date'] != null ? DateTime.parse(json['due_date']) : null,
      createdAt: DateTime.parse(json['created_at'] ?? DateTime.now().toIso8601String()),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'customer_id': customerId,
      'amount': amountCentimes,
      'status': status,
      'due_date': dueDate?.toIso8601String(),
      'created_at': createdAt.toIso8601String(),
    };
  }
}
