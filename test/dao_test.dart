// Tests d'intégration des accès base (DAO) sur une VRAIE base SQLite en mémoire :
// file d'envoi, curseurs de synchronisation, et DAO communs (BaseDao).

import 'package:ecahier/database/credit_dao.dart';
import 'package:ecahier/database/customer_dao.dart';
import 'package:ecahier/database/database.dart';
import 'package:ecahier/database/payment_dao.dart';
import 'package:ecahier/database/sync_meta_dao.dart';
import 'package:ecahier/database/sync_queue_dao.dart';
import 'package:ecahier/models/credit.dart';
import 'package:ecahier/models/customer.dart';
import 'package:ecahier/models/payment.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

void main() {
  late Database db;

  setUpAll(() {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  });

  setUp(() async {
    db = await databaseFactoryFfi.openDatabase(
      inMemoryDatabasePath,
      options: OpenDatabaseOptions(
        version: DatabaseHelper.schemaVersion,
        onCreate: DatabaseHelper.createSchema,
        singleInstance: false,
      ),
    );
    DatabaseHelper.instance.useDatabase(db);
  });

  tearDown(() async {
    await db.close();
    DatabaseHelper.instance.useDatabase(null);
  });

  final created = DateTime.utc(2026, 11, 1, 10);

  Customer customer(String id, String name) =>
      Customer(id: id, name: name, createdAt: created);

  Credit credit(String id, {int amount = 5000}) => Credit(
        id: id,
        customerId: 'c1',
        amount: amount,
        description: '',
        dueDate: created.add(const Duration(days: 30)),
        createdAt: created,
      );

  Payment payment(String id, String creditId, int amount) => Payment(
        id: id,
        customerId: 'c1',
        creditId: creditId,
        amount: amount,
        method: 'cash',
        createdAt: created,
      );

  SyncEntry entry(String recordId) => SyncEntry(
        tableName: 'customers',
        recordId: recordId,
        action: 'insert',
        payload: '{"id":"$recordId"}',
        createdAt: created,
      );

  group('SyncQueueDao', () {
    final dao = SyncQueueDao();

    test('les entrées en attente sortent dans l\'ordre de création', () async {
      for (final id in ['a', 'b', 'c']) {
        await dao.insert(entry(id));
      }

      final pending = await dao.getPending();

      expect(pending.map((e) => e.recordId), ['a', 'b', 'c']);
      expect(pending.every((e) => e.state == SyncState.pending), isTrue);
    });

    test('markSynced sort l\'entrée de la file ; deleteAllSynced la purge',
        () async {
      await dao.insert(entry('a'));
      await dao.insert(entry('b'));
      final first = (await dao.getPending()).first;

      await dao.markSynced(first.id!);

      expect(await dao.count(SyncState.pending), 1);
      expect(await dao.count(SyncState.synced), 1);
      expect(await dao.deleteAllSynced(), 1);
      expect(await dao.count(SyncState.synced), 0);
    });

    test('markFailed garde le motif ; retryFailed remet en attente et efface '
        'le motif', () async {
      await dao.insert(entry('a'));
      final id = (await dao.getPending()).single.id!;

      await dao.markFailed(id, 'Nom invalide');
      final failed = (await dao.getFailed()).single;
      expect(failed.lastError, 'Nom invalide');
      expect(await dao.getPending(), isEmpty);

      expect(await dao.retryFailed(), 1);
      final back = (await dao.getPending()).single;
      expect(back.lastError, isNull);
      expect(back.state, SyncState.pending);
    });

    test('retryFailed ne touche ni les envoyés ni les en attente', () async {
      await dao.insert(entry('a'));
      await dao.insert(entry('b'));
      final ids = (await dao.getPending()).map((e) => e.id!).toList();
      await dao.markSynced(ids[0]);

      expect(await dao.retryFailed(), 0);
      expect(await dao.count(SyncState.synced), 1);
      expect(await dao.count(SyncState.pending), 1);
    });

    test('l\'écriture et la file participent à la même transaction',
        () async {
      // Si la transaction échoue, ni le client ni l'envoi ne subsistent.
      await expectLater(
        db.transaction((txn) async {
          await CustomerDao().insert(customer('c1', 'Awa'), executor: txn);
          await dao.insert(entry('c1'), executor: txn);
          throw StateError('coupure');
        }),
        throwsA(isA<StateError>()),
      );

      expect(await CustomerDao().getAll(), isEmpty);
      expect(await dao.count(SyncState.pending), 0);
    });
  });

  group('SyncMetaDao', () {
    final dao = SyncMetaDao();

    test('valeur absente : null', () async {
      expect(await dao.get('cursor_customers'), isNull);
    });

    test('set puis get ; un second set remplace', () async {
      await dao.set('cursor_customers', 'a');
      await dao.set('cursor_customers', 'b');

      expect(await dao.get('cursor_customers'), 'b');
    });

    test('les curseurs des ressources sont indépendants', () async {
      await dao.set(SyncMetaDao.cursorKey('customers'), 'x');
      await dao.set(SyncMetaDao.cursorKey('credits'), 'y');

      expect(await dao.get(SyncMetaDao.cursorKey('customers')), 'x');
      expect(await dao.get(SyncMetaDao.cursorKey('credits')), 'y');
      expect(await dao.get(SyncMetaDao.cursorKey('payments')), isNull);
    });

    test('annulé avec la transaction qui l\'écrit', () async {
      await expectLater(
        db.transaction((txn) async {
          await dao.set('cursor_customers', 'z', executor: txn);
          throw StateError('coupure');
        }),
        throwsA(isA<StateError>()),
      );

      expect(await dao.get('cursor_customers'), isNull);
    });
  });

  group('BaseDao (via CustomerDao)', () {
    final dao = CustomerDao();

    test('insert refuse un id déjà utilisé (pas d\'écrasement muet)', () async {
      await dao.insert(customer('c1', 'Awa'));

      await expectLater(
          dao.insert(customer('c1', 'Autre')), throwsA(isA<DatabaseException>()));
      expect((await dao.getById('c1'))!.name, 'Awa');
    });

    test('upsertAll remplace l\'existant et ajoute le nouveau', () async {
      await dao.insert(customer('c1', 'Ancien nom'));

      await db.transaction((txn) => dao.upsertAll(
          [customer('c1', 'Nouveau nom'), customer('c2', 'Moussa')],
          executor: txn));

      expect((await dao.getById('c1'))!.name, 'Nouveau nom');
      expect(await dao.getAll(), hasLength(2));
    });

    test('getAll trie par nom sans tenir compte de la casse', () async {
      for (final (id, name) in [('1', 'zoé'), ('2', 'Awa'), ('3', 'moussa')]) {
        await dao.insert(customer(id, name));
      }

      expect((await dao.getAll()).map((c) => c.name), ['Awa', 'moussa', 'zoé']);
    });

    test('getById d\'un id inconnu : null', () async {
      expect(await dao.getById('inconnu'), isNull);
    });
  });

  group('CreditDao et PaymentDao', () {
    test('updateStatus ne change que le statut', () async {
      final credits = CreditDao();
      await credits.insert(credit('k1', amount: 5000));

      await credits.updateStatus('k1', CreditStatus.partial);

      final back = (await credits.getById('k1'))!;
      expect(back.status, CreditStatus.partial);
      expect(back.amount, 5000);
    });

    test('totalForCredit additionne les paiements de CE crédit seulement',
        () async {
      final payments = PaymentDao();
      await payments.insert(payment('p1', 'k1', 1000));
      await payments.insert(payment('p2', 'k1', 2500));
      await payments.insert(payment('p3', 'k2', 9999));

      expect(await payments.totalForCredit('k1'), 3500);
      expect(await payments.totalForCredit('k2'), 9999);
      expect(await payments.totalForCredit('absent'), 0);
    });
  });
}
