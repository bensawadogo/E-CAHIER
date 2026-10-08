import 'package:sqflite/sqflite.dart';
import '../models/customer.dart';
import 'database.dart';

/// Data Access Object for Customer.
class CustomerDao {
  Future<Database> get _db => DatabaseHelper.instance.database;

  static const String tableName = 'customers';

  Future<List<Customer>> getAll() async {
    final db = await _db;
    final List<Map<String, dynamic>> maps = await db.query(
      tableName,
      orderBy: 'name ASC',
    );
    return maps.map((map) => _fromMap(map)).toList();
  }

  Future<Customer?> getById(String id) async {
    final db = await _db;
    final List<Map<String, dynamic>> maps = await db.query(
      tableName,
      where: 'id = ?',
      whereArgs: [id],
    );
    if (maps.isEmpty) return null;
    return _fromMap(maps.first);
  }

  Future<int> insert(Customer customer) async {
    final db = await _db;
    return db.insert(
      tableName,
      _toMap(customer),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<int> upsert(Customer customer) async {
    final db = await _db;
    return db.insert(
      tableName,
      _toMap(customer),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<int> delete(String id) async {
    final db = await _db;
    return db.delete(tableName, where: 'id = ?', whereArgs: [id]);
  }

  Future<int> updateBalances({
    required String customerId,
    required int totalCredit,
    required int totalPaid,
  }) async {
    final db = await _db;
    return db.update(
      tableName,
      {'total_credit': totalCredit, 'total_paid': totalPaid},
      where: 'id = ?',
      whereArgs: [customerId],
    );
  }

  Map<String, dynamic> _toMap(Customer c) {
    return {
      'id': c.id,
      'name': c.name,
      'phone': c.phone,
      'address': c.address,
      'notes': c.notes,
      'is_active': c.isActive ? 1 : 0,
      'created_at': c.createdAt.toIso8601String(),
      'total_credit': c.totalCredit,
      'total_paid': c.totalPaid,
    };
  }

  Customer _fromMap(Map<String, dynamic> map) {
    return Customer(
      id: map['id'],
      name: map['name'],
      phone: map['phone'],
      address: map['address'],
      notes: map['notes'],
      isActive: (map['is_active'] ?? 1) == 1,
      createdAt: DateTime.parse(map['created_at']),
      totalCredit: (map['total_credit'] as int?) ?? 0,
      totalPaid: (map['total_paid'] as int?) ?? 0,
    );
  }
}