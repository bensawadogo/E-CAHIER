import 'package:sqflite/sqflite.dart';
import 'database.dart';

/// Opération de synchronisation en attente.
class SyncEntry {
  final int? id;
  final String tableName;
  final String recordId;
  final String action;
  final String payload;
  final DateTime createdAt;
  final bool synced;

  SyncEntry({
    this.id,
    required this.tableName,
    required this.recordId,
    required this.action,
    required this.payload,
    required this.createdAt,
    this.synced = false,
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'table_name': tableName,
      'record_id': recordId,
      'action': action,
      'payload': payload,
      'created_at': createdAt.toIso8601String(),
      'synced': synced ? 1 : 0,
    };
  }

  factory SyncEntry.fromMap(Map<String, dynamic> map) {
    return SyncEntry(
      id: map['id'] as int?,
      tableName: map['table_name'] as String,
      recordId: map['record_id'] as String,
      action: map['action'] as String,
      payload: map['payload'] as String,
      createdAt: DateTime.parse(map['created_at'] as String),
      synced: (map['synced'] as int) == 1,
    );
  }
}

/// Data Access Object for the offline sync queue.
class SyncQueueDao {
  Future<Database> get _db => DatabaseHelper.instance.database;

  static const String tableName = 'sync_queue';

  Future<List<SyncEntry>> getPending() async {
    final db = await _db;
    final maps = await db.query(
      tableName,
      where: 'synced = ?',
      whereArgs: [0],
      orderBy: 'created_at ASC',
    );
    return maps.map((m) => SyncEntry.fromMap(m)).toList();
  }

  Future<int> insert(SyncEntry entry) async {
    final db = await _db;
    return db.insert(tableName, entry.toMap());
  }

  Future<int> markSynced(int id) async {
    final db = await _db;
    return db.update(
      tableName,
      {'synced': 1},
      where: 'id = ?',
      whereArgs: [id],
    );
  }

  Future<int> delete(int id) async {
    final db = await _db;
    return db.delete(tableName, where: 'id = ?', whereArgs: [id]);
  }

  Future<int> deleteAllSynced() async {
    final db = await _db;
    return db.delete(
      tableName,
      where: 'synced = ?',
      whereArgs: [1],
    );
  }
}
