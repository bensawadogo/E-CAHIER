import 'package:sqflite/sqflite.dart';
import '../models/payment.dart';
import 'database.dart';

/// Data Access Object for Payment.
class PaymentDao {
  Future<Database> get _db => DatabaseHelper.instance.database;

  static const String tableName = 'payments';

  Future<List<Payment>> getAll() async {
    final db = await _db;
    final List<Map<String, dynamic>> maps = await db.query(
      tableName,
      orderBy: 'created_at DESC',
    );
    return maps.map((map) => _fromMap(map)).toList();
  }

  Future<List<Payment>> getByCustomerId(String customerId) async {
    final db = await _db;
    final List<Map<String, dynamic>> maps = await db.query(
      tableName,
      where: 'customer_id = ?',
      whereArgs: [customerId],
      orderBy: 'created_at DESC',
    );
    return maps.map((map) => _fromMap(map)).toList();
  }

  Future<Payment?> getById(String id) async {
    final db = await _db;
    final List<Map<String, dynamic>> maps = await db.query(
      tableName,
      where: 'id = ?',
      whereArgs: [id],
    );
    if (maps.isEmpty) return null;
    return _fromMap(maps.first);
  }

  Future<int> insert(Payment payment) async {
    final db = await _db;
    return db.insert(
      tableName,
      _toMap(payment),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<int> upsert(Payment payment) async {
    final db = await _db;
    return db.insert(
      tableName,
      _toMap(payment),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<int> delete(String id) async {
    final db = await _db;
    return db.delete(tableName, where: 'id = ?', whereArgs: [id]);
  }

  Map<String, dynamic> _toMap(Payment p) {
    return {
      'id': p.id,
      'customer_id': p.customerId,
      'amount': p.amountCentimes,
      'method': p.method,
      'created_at': p.createdAt.toIso8601String(),
    };
  }

  Payment _fromMap(Map<String, dynamic> map) {
    return Payment(
      id: map['id'],
      customerId: map['customer_id'],
      amountCentimes: (map['amount'] as int?) ?? 0,
      method: map['method'] ?? 'cash',
      createdAt: DateTime.parse(map['created_at']),
    );
  }
}