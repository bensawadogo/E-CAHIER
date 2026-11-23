import 'package:sqflite/sqflite.dart';

import 'database.dart';

/// Accès SQLite commun aux clients, crédits et paiements.
///
/// Toutes les méthodes d'écriture acceptent un [DatabaseExecutor] pour
/// participer à une transaction (écriture + file de sync = tout ou rien).
abstract class BaseDao<T> {
  String get tableName;

  /// Clause ORDER BY par défaut de [getAll].
  String get defaultOrder;

  Map<String, Object?> toMap(T item);
  T fromMap(Map<String, Object?> map);

  Future<Database> get _db => DatabaseHelper.instance.database;

  Future<List<T>> getAll() async {
    final db = await _db;
    final rows = await db.query(tableName, orderBy: defaultOrder);
    return rows.map(fromMap).toList();
  }

  Future<T?> getById(String id, {DatabaseExecutor? executor}) async {
    final db = executor ?? await _db;
    final rows = await db.query(tableName,
        where: 'id = ?', whereArgs: [id], limit: 1);
    return rows.isEmpty ? null : fromMap(rows.first);
  }

  /// Nouvelle ligne : échoue si l'id existe déjà (jamais d'écrasement muet).
  Future<void> insert(T item, {DatabaseExecutor? executor}) async {
    final db = executor ?? await _db;
    await db.insert(tableName, toMap(item),
        conflictAlgorithm: ConflictAlgorithm.abort);
  }

  /// Insère ou remplace en un seul lot (données venues du serveur).
  Future<void> upsertAll(
    Iterable<T> items, {
    required DatabaseExecutor executor,
  }) async {
    final batch = executor.batch();
    for (final item in items) {
      batch.insert(tableName, toMap(item),
          conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }
}
