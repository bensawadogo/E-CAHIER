import 'package:sqflite/sqflite.dart';

import 'database.dart';

/// État d'une entrée de la file d'envoi.
class SyncState {
  static const int pending = 0;
  static const int synced = 1;

  /// Refusée par le serveur (donnée invalide) : ne sera pas renvoyée
  /// automatiquement, reste visible pour une relance manuelle.
  static const int failed = 2;
}

/// Opération de synchronisation à envoyer au serveur.
class SyncEntry {
  final int? id;
  final String tableName;
  final String recordId;
  final String action;
  final String payload;
  final DateTime createdAt;
  final int state;
  final String? lastError;

  const SyncEntry({
    this.id,
    required this.tableName,
    required this.recordId,
    required this.action,
    required this.payload,
    required this.createdAt,
    this.state = SyncState.pending,
    this.lastError,
  });

  Map<String, Object?> toMap() => {
        'id': id,
        'table_name': tableName,
        'record_id': recordId,
        'action': action,
        'payload': payload,
        'created_at': createdAt.toUtc().toIso8601String(),
        'synced': state,
        'last_error': lastError,
      };

  factory SyncEntry.fromMap(Map<String, Object?> map) => SyncEntry(
        id: map['id'] as int?,
        tableName: map['table_name'] as String,
        recordId: map['record_id'] as String,
        action: map['action'] as String,
        payload: map['payload'] as String,
        createdAt: DateTime.parse(map['created_at'] as String),
        state: map['synced'] as int? ?? SyncState.pending,
        lastError: map['last_error'] as String?,
      );
}

/// File d'attente d'envoi (offline-first).
class SyncQueueDao {
  Future<Database> get _db => DatabaseHelper.instance.database;

  static const String tableName = 'sync_queue';

  /// Ajoute une opération (à appeler dans la même transaction que l'écriture
  /// locale correspondante).
  Future<void> insert(SyncEntry entry, {DatabaseExecutor? executor}) async {
    final db = executor ?? await _db;
    await db.insert(tableName, entry.toMap()..remove('id'));
  }

  /// Entrées à envoyer, dans l'ordre de création (un crédit part toujours
  /// après son client, un paiement après son crédit).
  Future<List<SyncEntry>> getPending() => _byState(SyncState.pending);

  Future<List<SyncEntry>> getFailed() => _byState(SyncState.failed);

  Future<List<SyncEntry>> _byState(int state) async {
    final db = await _db;
    final rows = await db.query(tableName,
        where: 'synced = ?', whereArgs: [state], orderBy: 'id ASC');
    return rows.map(SyncEntry.fromMap).toList();
  }

  Future<int> count(int state) async {
    final db = await _db;
    final rows = await db.rawQuery(
        'SELECT COUNT(*) AS n FROM $tableName WHERE synced = ?', [state]);
    return (rows.first['n'] as int?) ?? 0;
  }

  Future<void> markSynced(int id) => _setState(id, SyncState.synced, null);

  Future<void> markFailed(int id, String error) =>
      _setState(id, SyncState.failed, error);

  Future<void> _setState(int id, int state, String? error) async {
    final db = await _db;
    await db.update(tableName, {'synced': state, 'last_error': error},
        where: 'id = ?', whereArgs: [id]);
  }

  /// Remet les entrées refusées en attente (relance manuelle).
  Future<int> retryFailed() async {
    final db = await _db;
    return db.update(tableName, {'synced': SyncState.pending, 'last_error': null},
        where: 'synced = ?', whereArgs: [SyncState.failed]);
  }

  /// Purge les entrées envoyées pour que la file ne grossisse pas sans fin.
  Future<int> deleteAllSynced() async {
    final db = await _db;
    return db.delete(tableName,
        where: 'synced = ?', whereArgs: [SyncState.synced]);
  }
}
