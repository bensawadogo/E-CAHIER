import 'package:sqflite/sqflite.dart';

import '../models/payment.dart';
import '../utils/parsing.dart';
import 'base_dao.dart';
import 'database.dart';

class PaymentDao extends BaseDao<Payment> {
  @override
  String get tableName => 'payments';

  @override
  String get defaultOrder => 'created_at DESC';

  /// Total déjà payé pour un crédit (somme calculée par SQLite, sans charger
  /// les lignes en mémoire).
  Future<int> totalForCredit(String creditId,
      {DatabaseExecutor? executor}) async {
    final db = executor ?? await DatabaseHelper.instance.database;
    final rows = await db.rawQuery(
        'SELECT COALESCE(SUM(amount), 0) AS total FROM payments '
        'WHERE credit_id = ?',
        [creditId]);
    return (rows.first['total'] as int?) ?? 0;
  }

  @override
  Map<String, Object?> toMap(Payment p) => {
        'id': p.id,
        'customer_id': p.customerId,
        'credit_id': p.creditId,
        'amount': p.amount,
        'method': p.method,
        'created_at': p.createdAt.toUtc().toIso8601String(),
      };

  @override
  Payment fromMap(Map<String, Object?> map) => Payment(
        id: map['id'] as String,
        customerId: map['customer_id'] as String,
        creditId: map['credit_id'] as String? ?? '',
        amount: map['amount'] as int? ?? 0,
        method: map['method'] as String? ?? 'cash',
        createdAt: parseServerDate(map['created_at']),
      );
}
