import 'package:sqflite/sqflite.dart';
import '../models/credit.dart';
import 'database.dart';

/// Data Access Object for Credit.
class CreditDao {
  Future<Database> get _db => DatabaseHelper.instance.database;

  static const String tableName = 'credits';

  Future<List<Credit>> getAll() async {
    final db = await _db;
    final List<Map<String, dynamic>> maps = await db.query(
      tableName,
      orderBy: 'created_at DESC',
    );
    return maps.map((map) => _fromMap(map)).toList();
  }

  Future<List<Credit>> getByCustomerId(String customerId) async {
    final db = await _db;
    final List<Map<String, dynamic>> maps = await db.query(
      tableName,
      where: 'customer_id = ?',
      whereArgs: [customerId],
      orderBy: 'created_at DESC',
    );
    return maps.map((map) => _fromMap(map)).toList();
  }

  Future<Credit?> getById(String id) async {
    final db = await _db;
    final List<Map<String, dynamic>> maps = await db.query(
      tableName,
      where: 'id = ?',
      whereArgs: [id],
    );
    if (maps.isEmpty) return null;
    return _fromMap(maps.first);
  }

  Future<int> insert(Credit credit) async {
    final db = await _db;
    return db.insert(
      tableName,
      _toMap(credit),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<int> upsert(Credit credit) async {
    final db = await _db;
    return db.insert(
      tableName,
      _toMap(credit),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<int> delete(String id) async {
    final db = await _db;
    return db.delete(tableName, where: 'id = ?', whereArgs: [id]);
  }

  Map<String, dynamic> _toMap(Credit c) {
    return {
      'id': c.id,
      'customer_id': c.customerId,
      'amount': c.amountCentimes,
      'status': c.status,
      'due_date': c.dueDate?.toIso8601String(),
      'created_at': c.createdAt.toIso8601String(),
    };
  }

  Credit _fromMap(Map<String, dynamic> map) {
    return Credit(
      id: map['id'],
      customerId: map['customer_id'],
      amountCentimes: (map['amount'] as int?) ?? 0,
      status: map['status'] ?? 'active',
      dueDate: map['due_date'] != null
          ? DateTime.parse(map['due_date'])
          : null,
      createdAt: DateTime.parse(map['created_at']),
    );
  }
}