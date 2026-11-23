import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path/path.dart';
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';

/// Base SQLite locale (offline-first) : clients, crédits, paiements et file
/// d'attente de synchronisation. Les montants sont des FCFA entiers.
class DatabaseHelper {
  static const String _databaseName = 'ecahier.db';
  /// Version du schéma (les tests ouvrent leurs bases avec la même valeur).
  static const int schemaVersion = 3;

  static final DatabaseHelper _instance = DatabaseHelper._();
  DatabaseHelper._();

  static DatabaseHelper get instance => _instance;

  Database? _database;

  Future<Database> get database async {
    return _database ??= await _initDatabase();
  }

  Future<Database> _initDatabase() async {
    final Directory documentsDirectory =
        await getApplicationDocumentsDirectory();
    return openAt(join(documentsDirectory.path, _databaseName));
  }

  /// Ouvre (ou crée) la base au chemin donné.
  static Future<Database> openAt(String path) {
    return openDatabase(
      path,
      version: schemaVersion,
      onCreate: createSchema,
      onUpgrade: migrate,
    );
  }

  /// Remplace la base utilisée (tests : base en mémoire).
  @visibleForTesting
  void useDatabase(Database? db) => _database = db;

  static Future<void> createSchema(Database db, int version) async {
    await db.execute('''
      CREATE TABLE customers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        notes TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        total_credit INTEGER NOT NULL DEFAULT 0,
        total_paid INTEGER NOT NULL DEFAULT 0
      )
    ''');

    await db.execute('''
      CREATE TABLE credits (
        id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        amount INTEGER NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        due_date TEXT,
        created_at TEXT NOT NULL
      )
    ''');

    await db.execute('''
      CREATE TABLE payments (
        id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        credit_id TEXT NOT NULL DEFAULT '',
        amount INTEGER NOT NULL,
        method TEXT NOT NULL DEFAULT 'cash',
        created_at TEXT NOT NULL
      )
    ''');

    await db.execute(
        'CREATE INDEX idx_credits_customer_id ON credits(customer_id)');
    await db.execute(
        'CREATE INDEX idx_payments_customer_id ON payments(customer_id)');
    await db.execute(
        'CREATE INDEX idx_payments_credit_id ON payments(credit_id)');

    // synced : 0 = à envoyer, 1 = envoyé, 2 = refusé par le serveur.
    await db.execute('''
      CREATE TABLE sync_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_name TEXT NOT NULL,
        record_id TEXT NOT NULL,
        action TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        synced INTEGER NOT NULL DEFAULT 0,
        last_error TEXT
      )
    ''');
    await db.execute('CREATE INDEX idx_sync_queue_synced ON sync_queue(synced)');
    await _createSyncMeta(db);
  }

  /// Petites valeurs de synchronisation (curseurs de lecture incrémentale).
  static Future<void> _createSyncMeta(Database db) => db.execute('''
      CREATE TABLE IF NOT EXISTS sync_meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      )
    ''');

  static Future<void> migrate(
    Database db,
    int oldVersion,
    int newVersion,
  ) async {
    if (oldVersion < 2) {
      // v1 stockait des « centimes » (FCFA x 100) alors que le serveur compte
      // en FCFA : on convertit.
      await db.execute('UPDATE credits SET amount = amount / 100');
      await db.execute('UPDATE payments SET amount = amount / 100');
      await db.execute("UPDATE credits SET status = 'pending' "
          "WHERE status = 'active'");
      await db.execute("ALTER TABLE credits ADD COLUMN description TEXT "
          "NOT NULL DEFAULT ''");
      await db.execute("ALTER TABLE payments ADD COLUMN credit_id TEXT "
          "NOT NULL DEFAULT ''");
      await db.execute(
          'CREATE INDEX IF NOT EXISTS idx_payments_credit_id '
          'ON payments(credit_id)');
      await db.execute('ALTER TABLE sync_queue ADD COLUMN last_error TEXT');
      // Les anciennes entrées en attente ont un format que le serveur
      // refuse (montants x100, pas de credit_id) : on ne les renvoie pas
      // aveuglément, on les met « en erreur » pour qu'elles restent visibles.
      await db.execute("UPDATE sync_queue SET synced = 2, "
          "last_error = 'Ancien format (avant la version 2)' "
          'WHERE synced = 0');
    }
    if (oldVersion < 3) {
      // Pas de curseur au départ : le premier téléchargement est complet, les
      // suivants ne ramènent que les changements.
      await _createSyncMeta(db);
    }
  }
}
