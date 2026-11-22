// Tests du repository avec une API SIMULÉE (mocktail) et une vraie base SQLite
// en mémoire. On ne teste plus le HTTP (voir api_service_test.dart) mais les
// DÉCISIONS du repository : que fait-il quand l'API échoue de telle ou telle
// façon, dans quel ordre envoie-t-il, quand télécharge-t-il, où range-t-il son
// curseur.

import 'dart:convert';
import 'dart:io';

import 'package:ecahier/database/database.dart';
import 'package:ecahier/database/sync_meta_dao.dart';
import 'package:ecahier/models/customer.dart';
import 'package:ecahier/repositories/ecahier_repository.dart';
import 'package:ecahier/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  late Database db;
  late MockApiService api;
  late EcahierRepository repo;

  // --- Comportements de l'API simulée ------------------------------------
  void stubReads({
    Pulled<Customer> customers = const Pulled([], null),
  }) {
    when(() => api.getCustomers(updatedSince: any(named: 'updatedSince')))
        .thenAnswer((_) async => customers);
    when(() => api.getCredits(updatedSince: any(named: 'updatedSince')))
        .thenAnswer((_) async => const Pulled([], null));
    when(() => api.getPayments(updatedSince: any(named: 'updatedSince')))
        .thenAnswer((_) async => const Pulled([], null));
  }

  void offline() {
    when(() => api.post(any(), any()))
        .thenAnswer((_) async => throw const SocketException('pas de réseau'));
    stubReads();
  }

  void online() {
    when(() => api.post(any(), any())).thenAnswer((_) async {});
    stubReads();
  }

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
    api = MockApiService();
    repo = EcahierRepository(api: api);
    offline(); // par défaut : pas de réseau (états déterministes)
  });

  tearDown(() async {
    await db.close();
    DatabaseHelper.instance.useDatabase(null);
  });

  /// Attend l'envoi de fond lancé par les écritures, puis oublie les appels.
  Future<void> settle() async {
    await repo.sync(pull: false);
    clearInteractions(api);
  }

  Future<void> seedThreeEntries() async {
    final customer = await repo.createCustomer(name: 'Awa');
    final credit =
        await repo.createCredit(customerId: customer.id, amount: 5000);
    await repo.createPayment(creditId: credit.id, amount: 1000);
    await settle();
  }

  Customer remoteCustomer(String id) => Customer(
      id: id, name: 'Distant $id', createdAt: DateTime.utc(2026, 11, 1));

  group('envoi', () {
    test('part dans l\'ordre client -> crédit -> paiement', () async {
      await seedThreeEntries();
      online();

      await repo.sync(pull: false);

      verifyInOrder([
        () => api.post('customers', any()),
        () => api.post('credits', any()),
        () => api.post('payments', any()),
      ]);
      expect(await repo.pendingCount(), 0);
    });

    test('envoie le corps exact préparé par le modèle (id de l\'app)',
        () async {
      final customer = await repo.createCustomer(name: '  Awa  ', phone: '70');
      await settle();
      online();

      await repo.sync(pull: false);

      final body = verify(() => api.post('customers', captureAny()))
          .captured
          .single as Map<String, dynamic>;
      expect(body['id'], customer.id);
      expect(body['name'], 'Awa'); // espaces retirés
      expect(body['phone'], '70');
    });

    test('un refus 422 : l\'élément est mis de côté, les suivants partent',
        () async {
      await seedThreeEntries();
      var first = true;
      when(() => api.post(any(), any())).thenAnswer((_) async {
        if (first) {
          first = false;
          throw const ApiException(422, 'Nom invalide');
        }
      });

      await repo.sync(pull: false);

      verify(() => api.post(any(), any())).called(3); // les 3 ont été tentés
      final status = await repo.getSyncStatus();
      expect(status.failed, 1);
      expect(status.pending, 0);
      expect(status.failedEntries.single.lastError, 'Nom invalide');
    });

    test('jeton refusé (401) : arrêt immédiat, tout reste en attente',
        () async {
      await seedThreeEntries();
      when(() => api.post(any(), any()))
          .thenAnswer((_) async => throw const ApiException(401, 'non'));

      await repo.sync(pull: false);

      verify(() => api.post(any(), any())).called(1); // pas d'acharnement
      final status = await repo.getSyncStatus();
      expect(status.pending, 3);
      expect(status.failed, 0);
      expect(status.lastError, contains('Accès refusé'));
    });

    test('serveur en panne (503) : arrêt, rien n\'est marqué « refusé »',
        () async {
      await seedThreeEntries();
      when(() => api.post(any(), any()))
          .thenAnswer((_) async => throw const ApiException(503, 'down'));

      await repo.sync(pull: false);

      verify(() => api.post(any(), any())).called(1);
      final status = await repo.getSyncStatus();
      expect(status.pending, 3);
      expect(status.failed, 0);
      expect(status.lastError, contains('Serveur indisponible'));
    });

    test('coupure réseau : arrêt, message dédié', () async {
      await seedThreeEntries();

      await repo.sync(pull: false);

      verify(() => api.post(any(), any())).called(1);
      expect((await repo.getSyncStatus()).lastError, contains('Pas de connexion'));
    });

    test('retryFailed remet les refus en file et les renvoie', () async {
      await repo.createCustomer(name: 'Awa');
      await settle();
      when(() => api.post(any(), any()))
          .thenAnswer((_) async => throw const ApiException(422, 'non'));
      await repo.sync(pull: false);
      expect((await repo.getSyncStatus()).failed, 1);
      clearInteractions(api); // on ne compte que la relance
      online();

      await repo.retryFailed();

      verify(() => api.post('customers', any())).called(1);
      final status = await repo.getSyncStatus();
      expect(status.failed, 0);
      expect(status.pending, 0);
    });

    test('une écriture ne lève jamais d\'erreur réseau à l\'appelant',
        () async {
      // L'API lève une exception inattendue : l'écran ne doit rien voir.
      when(() => api.post(any(), any())).thenAnswer((_) async => throw StateError('bug'));

      final customer = await repo.createCustomer(name: 'Awa');
      await repo.sync(pull: false);

      expect((await repo.getCustomers()).single.id, customer.id);
      expect(await repo.pendingCount(), 1); // la donnée n'est pas perdue
    });
  });

  group('téléchargement', () {
    test('ne télécharge pas tant qu\'il reste des éléments à envoyer',
        () async {
      await repo.createCustomer(name: 'Local');
      await settle();

      await repo.sync(); // toujours hors ligne : l'envoi échoue

      verifyNever(() => api.getCustomers(updatedSince: any(named: 'updatedSince')));
    });

    test('premier téléchargement sans curseur, le suivant avec celui reçu',
        () async {
      online();
      stubReads(customers: Pulled([remoteCustomer('r1')], 'curseur-1'));

      await repo.sync();
      await repo.sync(); // forcé (pull: true par défaut)

      verifyInOrder([
        () => api.getCustomers(updatedSince: null),
        () => api.getCustomers(updatedSince: 'curseur-1'),
      ]);
      expect(await SyncMetaDao().get(SyncMetaDao.cursorKey('customers')),
          'curseur-1');
    });

    test('les données reçues sont écrites en local', () async {
      online();
      stubReads(customers: Pulled([remoteCustomer('r1'), remoteCustomer('r2')], 'c'));

      await repo.sync();

      expect((await repo.getCustomers()).map((c) => c.id).toSet(), {'r1', 'r2'});
    });

    test('curseur absent de la réponse : l\'ancien est conservé', () async {
      online();
      stubReads(customers: Pulled([remoteCustomer('r1')], 'ancien'));
      await repo.sync();
      stubReads(customers: const Pulled([], null)); // réponse sans curseur

      await repo.sync();

      expect(await SyncMetaDao().get(SyncMetaDao.cursorKey('customers')),
          'ancien');
    });

    test('lecture qui échoue en cours de route : rien n\'est écrit, curseur '
        'inchangé', () async {
      online();
      stubReads(customers: Pulled([remoteCustomer('r1')], 'c1'));
      when(() => api.getCredits(updatedSince: any(named: 'updatedSince')))
          .thenAnswer((_) async => throw const ApiException(500, 'boom'));

      await repo.sync();

      expect(await repo.getCustomers(), isEmpty); // pas de base « à moitié »
      expect(await SyncMetaDao().get(SyncMetaDao.cursorKey('customers')), isNull);
      expect((await repo.getSyncStatus()).lastError,
          contains('Impossible de récupérer'));
    });

    test('jeton refusé pendant la lecture : message dédié', () async {
      online();
      when(() => api.getCustomers(updatedSince: any(named: 'updatedSince')))
          .thenAnswer((_) async => throw const ApiException(401, 'non'));

      await repo.sync();

      expect((await repo.getSyncStatus()).lastError, contains('Accès refusé'));
    });

    test('un envoi de fond ne retélécharge pas : ménage la connexion',
        () async {
      online();
      await repo.sync(); // premier téléchargement
      clearInteractions(api);

      await repo.sync(pull: false);
      await repo.sync(pull: false);

      verifyNever(() => api.getCustomers(updatedSince: any(named: 'updatedSince')));
    });
  });

  group('écritures locales (sans réseau)', () {
    test('une création n\'appelle l\'API qu\'en arrière-plan, après l\'écriture',
        () async {
      final customer = await repo.createCustomer(name: 'Awa');

      // Déjà lisible localement, avant tout envoi abouti.
      expect((await repo.getCustomers()).single.id, customer.id);
      expect(await repo.pendingCount(), 1);
    });

    test('le payload mis en file est du JSON valide pour le serveur', () async {
      await repo.createCustomer(name: 'Awa');
      await settle();

      final rows = await db.query('sync_queue');
      final payload = json.decode(rows.single['payload'] as String) as Map;
      expect(payload.keys, containsAll(['id', 'name']));
      expect(rows.single['table_name'], 'customers');
      expect(rows.single['action'], 'insert');
    });

    test('un paiement refusé localement n\'est jamais envoyé', () async {
      final customer = await repo.createCustomer(name: 'Awa');
      final credit =
          await repo.createCredit(customerId: customer.id, amount: 1000);
      await settle();

      await expectLater(
        repo.createPayment(creditId: credit.id, amount: 5000),
        throwsA(isA<RepositoryException>()),
      );
      await repo.sync(pull: false);

      verifyNever(() => api.post('payments', any()));
      expect(await repo.pendingCount(), 2); // client + crédit seulement
    });
  });
}
