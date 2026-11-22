import 'package:sqflite/sqflite.dart';

import '../models/credit.dart';
import '../utils/parsing.dart';
import 'base_dao.dart';
import 'database.dart';

class CreditDao extends BaseDao<Credit> {
  @override
  String get tableName => 'credits';

  @override
  String get defaultOrder => 'created_at DESC';

  Future<void> updateStatus(String id, String status,
      {DatabaseExecutor? executor}) async {
    final db = executor ?? await DatabaseHelper.instance.database;
    await db.update(tableName, {'status': status},
        where: 'id = ?', whereArgs: [id]);
  }

  @override
  Map<String, Object?> toMap(Credit c) => {
        'id': c.id,
        'customer_id': c.customerId,
        'amount': c.amount,
        'description': c.description,
        'status': c.status,
        'due_date': c.dueDate?.toUtc().toIso8601String(),
        'created_at': c.createdAt.toUtc().toIso8601String(),
      };

  @override
  Credit fromMap(Map<String, Object?> map) => Credit(
        id: map['id'] as String,
        customerId: map['customer_id'] as String,
        amount: map['amount'] as int? ?? 0,
        description: map['description'] as String? ?? '',
        status: map['status'] as String? ?? CreditStatus.pending,
        dueDate: map['due_date'] != null
            ? parseServerDate(map['due_date'])
            : null,
        createdAt: parseServerDate(map['created_at']),
      );
}
