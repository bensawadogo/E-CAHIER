import 'package:sqflite/sqflite.dart';

import 'database.dart';

/// Curseurs de lecture incrémentale : pour chaque ressource, la date de
/// dernière modification vue sur le serveur. Au prochain téléchargement, on ne
/// redemande que ce qui a changé depuis (économie de données sur 2G/3G).
class SyncMetaDao {
  /// Clé du curseur d'une ressource (`customers`, `credits`, `payments`).
  static String cursorKey(String resource) => 'cursor_$resource';

  Future<String?> get(String key) async {
    final db = await DatabaseHelper.instance.database;
    final rows = await db.query('sync_meta',
        where: 'key = ?', whereArgs: [key], limit: 1);
    return rows.isEmpty ? null : rows.first['value'] as String;
  }

  Future<void> set(String key, String value, {DatabaseExecutor? executor}) async {
    final db = executor ?? await DatabaseHelper.instance.database;
    await db.insert(
      'sync_meta',
      {'key': key, 'value': value},
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }
}
