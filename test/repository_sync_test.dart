// Repository offline-first sur une VRAIE base SQLite (en mémoire) avec un
// faux serveur HTTP : écriture locale immédiate, envoi idempotent, coupures
// réseau, refus du serveur, migration de l'ancienne base.
//
// Chaque écriture lance un envoi en arrière-plan (comme dans l'app). Pour des
// états déterministes, le faux serveur démarre HORS LIGNE : on écrit, on
// « règle » (settle) l'envoi de fond, puis on bascule en ligne.

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:ecahier/database/database.dart';
import 'package:ecahier/database/sync_queue_dao.dart';
import 'package:ecahier/models/credit.dart';
import 'package:ecahier/repositories/ecahier_repository.dart';
import 'package:ecahier/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

typedef Handler = Future<http.Response> Function(http.Request request);

http.Response jsonResponse(Object body, [int status = 200]) => http.Response(
    json.encode(body), status,
    headers: {'content-type': 'application/json'});

String lastSegment(Uri url) =>
    url.pathSegments.where((s) => s.isNotEmpty).last;

/// Faux serveur : enregistre les requêtes et répond selon [handler].
class FakeServer {
  final List<http.Request> requests = [];

  /// Hors ligne par défaut.
  Handler handler = offline;

  static Future<http.Response> offline(http.Request _) async =>
      throw const SocketException('pas de réseau');

  /// Serveur qui accepte tout (POST renvoie le corps, GET renvoie une liste vide).
  static Future<http.Response> healthy(http.Request request) async {
    if (request.method == 'POST') {
      return http.Response(request.body, 201,
          headers: {'content-type': 'application/json'});
    }
    return jsonResponse({
      lastSegment(request.url): [],
      'total': 0,
      'page': 1,
      'page_size': 100,
    });
  }

  List<Map<String, dynamic>> posted(String resource) => [
        for (final r in requests)
          if (r.method == 'POST' && lastSegment(r.url) == resource)
            json.decode(r.body) as Map<String, dynamic>,
      ];

  int get postCount => requests.where((r) => r.method == 'POST').length;
  Iterable<http.Request> get gets => requests.where((r) => r.method == 'GET');

  http.Client get client => MockClient((request) {
        requests.add(request);
        return handler(request);
      });
}

void main() {
  late Database db;
  late FakeServer server;
  late EcahierRepository repo;

  EcahierRepository newRepo({String token = ''}) => EcahierRepository(
        api: ApiService(
          client: server.client,
          baseUrl: 'http://test/api',
          authToken: token,
          retryDelay: Duration.zero,
        ),
      );

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
    server = FakeServer();
    repo = newRepo();
  });

  tearDown(() async {
    await db.close();
    DatabaseHelper.instance.useDatabase(null);
  });

  /// Attend la fin de l'envoi de fond lancé par les écritures.
  Future<void> settle() => repo.sync(pull: false);

  /// Passe en ligne et oublie les requêtes déjà faites.
  void goOnline([Handler? handler]) {
    server.handler = handler ?? FakeServer.healthy;
    server.requests.clear();
  }

  Future<(String customerId, String creditId)> seedCreditedCustomer(
      {int amount = 5000}) async {
    final customer = await repo.createCustomer(name: 'Awa', phone: '70000000');
    final credit =
        await repo.createCredit(customerId: customer.id, amount: amount);
    return (customer.id, credit.id);
  }

  group('écriture locale', () {
    test('rend la main sans attendre le serveur', () async {
      final gate = Completer<http.Response>(); // le serveur ne répond pas
      server.handler = (_) => gate.future;

      final customer = await repo.createCustomer(name: '  Awa  ');

      expect(customer.name, 'Awa');
      expect((await repo.getCustomers()).single.id, customer.id);
      expect(await repo.pendingCount(), 1);

      gate.complete(http.Response('', 503)); // libère l'envoi de fond
      await settle();
    });

    test('refuse un nom vide et un montant nul', () async {
      await expectLater(repo.createCustomer(name: '   '),
          throwsA(isA<RepositoryException>()));
      await expectLater(repo.createCredit(customerId: 'x', amount: 0),
          throwsA(isA<RepositoryException>()));
      expect(await repo.pendingCount(), 0);
    });

    test('un crédit a une échéance par défaut à 30 jours (comme le serveur)',
        () async {
      final (_, creditId) = await seedCreditedCustomer();
      final credit =
          (await repo.getCredits()).firstWhere((c) => c.id == creditId);
      final days = credit.dueDate!.difference(credit.createdAt).inDays;
      expect(days, anyOf(29, 30));
    });

    test('les écritures sont notifiées aux écrans', () async {
      var notified = 0;
      repo.addListener(() => notified++);
      await repo.createCustomer(name: 'Awa');
      expect(notified, greaterThan(0));
      await settle();
    });
  });

  group('envoi (sync)', () {
    test('envoie dans l\'ordre client → crédit → paiement, avec les id locaux',
        () async {
      final (customerId, creditId) = await seedCreditedCustomer();
      await repo.createPayment(creditId: creditId, amount: 2000);
      await settle(); // hors ligne : tout reste en file
      goOnline();

      await repo.sync(pull: false);

      expect([
        for (final r in server.requests)
          if (r.method == 'POST') lastSegment(r.url)
      ], ['customers', 'credits', 'payments']);
      expect(server.posted('customers').single['id'], customerId);
      expect(server.posted('credits').single['id'], creditId);
      final payment = server.posted('payments').single;
      expect(payment['credit_id'], creditId);
      expect(payment['amount'], 2000);
      expect(await repo.pendingCount(), 0);
    });

    test('ne renvoie jamais deux fois ce qui est déjà parti', () async {
      await seedCreditedCustomer();
      await settle();
      goOnline();
      await repo.sync(pull: false);
      final afterFirst = server.postCount;
      expect(afterFirst, 2);

      await repo.sync(pull: false);
      await repo.sync(pull: false);
      expect(server.postCount, afterFirst);
    });

    test('hors ligne : rien n\'est perdu, tout part au retour du réseau',
        () async {
      final (_, creditId) = await seedCreditedCustomer();
      await repo.createPayment(creditId: creditId, amount: 1000);
      await settle();

      var status = await repo.getSyncStatus();
      expect(status.pending, 3);
      expect(status.failed, 0);
      expect(status.lastError, isNotNull);

      goOnline(); // le réseau revient
      await repo.sync(pull: false);
      expect(await repo.pendingCount(), 0);
      expect(server.postCount, 3);
      status = await repo.getSyncStatus();
      expect(status.lastError, isNull);
    });

    test('serveur en panne (503) : on garde en file, sans marquer « refusé »',
        () async {
      await seedCreditedCustomer();
      await settle();
      goOnline((_) async => http.Response('', 503));
      await repo.sync(pull: false);

      final status = await repo.getSyncStatus();
      expect(status.pending, 2);
      expect(status.failed, 0);
    });

    test('coupure au premier envoi : les suivants ne sont pas tentés',
        () async {
      await seedCreditedCustomer();
      await settle();
      goOnline(FakeServer.offline);

      await repo.sync(pull: false);

      expect(server.posted('customers').length, 2); // 2 tentatives du client
      expect(server.posted('credits'), isEmpty);
    });

    test('donnée refusée (422) : marquée en erreur, visible, pas de boucle',
        () async {
      await repo.createCustomer(name: 'Awa');
      await settle();
      goOnline((_) async => jsonResponse({'detail': 'Nom invalide'}, 422));
      await repo.sync(pull: false);

      var status = await repo.getSyncStatus();
      expect(status.pending, 0);
      expect(status.failed, 1);
      expect(status.failedEntries.single.lastError, 'Nom invalide');

      final before = server.postCount;
      await repo.sync(pull: false);
      expect(server.postCount, before, reason: 'ne doit pas être renvoyé');

      // Relance manuelle : repart en attente puis part pour de bon.
      goOnline();
      await repo.retryFailed();
      status = await repo.getSyncStatus();
      expect(status.pending, 0);
      expect(status.failed, 0);
      expect(server.postCount, 1);
    });

    test('un refus n\'empêche pas l\'envoi des autres éléments', () async {
      await repo.createCustomer(name: 'Mauvais');
      await repo.createCustomer(name: 'Bon');
      await settle();
      goOnline((request) async {
        final body = json.decode(request.body) as Map<String, dynamic>;
        return body['name'] == 'Mauvais'
            ? jsonResponse({'detail': 'refusé'}, 400)
            : http.Response(request.body, 201);
      });
      await repo.sync(pull: false);

      final status = await repo.getSyncStatus();
      expect(status.failed, 1);
      expect(status.pending, 0);
    });

    test('jeton refusé (401) : on s\'arrête et on garde tout en attente',
        () async {
      await seedCreditedCustomer();
      await settle();
      goOnline((_) async => jsonResponse({'detail': 'Unauthorized'}, 401));
      await repo.sync(pull: false);

      final status = await repo.getSyncStatus();
      expect(status.pending, 2);
      expect(status.failed, 0);
      expect(status.lastError, contains('Accès refusé'));
      expect(server.postCount, 1,
          reason: 'inutile d\'insister avec un jeton refusé');
    });

    test('envoie le jeton Bearer quand il est configuré', () async {
      final secured = newRepo(token: 'secret');
      await secured.createCustomer(name: 'Awa');
      await secured.sync(pull: false);
      expect(server.requests, isNotEmpty);
      expect(server.requests.every((r) => r.headers['Authorization'] == 'Bearer secret'),
          isTrue);
    });

    test('sync() attend la synchro déjà en cours au lieu de rendre la main',
        () async {
      await repo.createCustomer(name: 'Awa');
      await settle();
      final gate = Completer<http.Response>();
      goOnline((_) => gate.future);

      final first = repo.sync(pull: false); // envoi bloqué sur le réseau
      var secondDone = false;
      final second = repo.sync(pull: false).then((_) => secondDone = true);
      await Future<void>.delayed(const Duration(milliseconds: 50));
      expect(secondDone, isFalse, reason: 'doit attendre la fin de la première');

      gate.complete(http.Response('{}', 201));
      await Future.wait([first, second]);
      expect(secondDone, isTrue);
      expect(await repo.pendingCount(), 0);
    });
  });

  group('paiements', () {
    test('met le crédit à jour : partiel puis payé', () async {
      final (_, creditId) = await seedCreditedCustomer(amount: 5000);
      Future<Credit> credit() async =>
          (await repo.getCredits()).firstWhere((c) => c.id == creditId);

      await repo.createPayment(creditId: creditId, amount: 2000);
      expect((await credit()).status, CreditStatus.partial);

      await repo.createPayment(creditId: creditId, amount: 3000);
      expect((await credit()).status, CreditStatus.paid);
      await settle();
    });

    test('refuse un paiement supérieur au reste à payer', () async {
      final (_, creditId) = await seedCreditedCustomer(amount: 5000);
      await repo.createPayment(creditId: creditId, amount: 4000);
      await expectLater(
        repo.createPayment(creditId: creditId, amount: 2000),
        throwsA(isA<RepositoryException>()
            .having((e) => e.message, 'message', contains('1 000 FCFA'))),
      );
      await settle();
      // Rien n'a été écrit pour la tentative refusée.
      expect((await repo.getPayments()).length, 1);
      expect(await repo.pendingCount(), 3); // client + crédit + 1 paiement
    });

    test('refuse un paiement sur un crédit déjà soldé', () async {
      final (_, creditId) = await seedCreditedCustomer(amount: 1000);
      await repo.createPayment(creditId: creditId, amount: 1000);
      await expectLater(repo.createPayment(creditId: creditId, amount: 1),
          throwsA(isA<RepositoryException>()));
      await settle();
    });

    test('le paiement est rattaché au client du crédit', () async {
      final (customerId, creditId) = await seedCreditedCustomer();
      final payment = await repo.createPayment(creditId: creditId, amount: 100);
      expect(payment.customerId, customerId);
      await settle();
    });

    test('Snapshot calcule le reste à payer', () async {
      final (_, creditId) = await seedCreditedCustomer(amount: 5000);
      await repo.createPayment(creditId: creditId, amount: 1500);
      final data = await repo.loadSnapshot();
      expect(data.remaining(data.credits.single), 3500);
      await settle();
    });
  });

  group('lecture du serveur (pull)', () {
    Map<String, dynamic> customerJson(int i) => {
          'id': 'c$i',
          'name': 'Client $i',
          'phone': '',
          'address': '',
          'notes': '',
          'photo_path': '',
          'total_credit': '5000',
          'total_paid': '0.0',
          'balance': '5000',
          'is_active': true,
          'created_at': '2026-11-11T10:00:00',
          'updated_at': '2026-11-11T10:00:00',
          'sync_status': 'pending',
        };

    test('lit l\'enveloppe paginée et les Decimal en chaînes', () async {
      goOnline((request) async {
        switch (lastSegment(request.url)) {
          case 'customers':
            return jsonResponse({
              'customers': [customerJson(1)],
              'total': 1,
              'page': 1,
              'page_size': 100,
            });
          case 'credits':
            return jsonResponse({
              'credits': [
                {
                  'id': 'k1',
                  'customer_id': 'c1',
                  'amount': '5000',
                  'description': '',
                  'due_date': '2020-01-01T00:00:00Z',
                  'status': 'pending',
                  'is_overdue': true,
                  'created_at': '2019-12-01T00:00:00Z',
                  'updated_at': '2019-12-01T00:00:00Z',
                  'sync_status': 'pending',
                }
              ],
              'total': 1,
              'page': 1,
              'page_size': 100,
            });
          default:
            return jsonResponse(
                {'payments': [], 'total': 0, 'page': 1, 'page_size': 100});
        }
      });

      await repo.sync();

      final data = await repo.loadSnapshot();
      expect(data.customers.single.totalCredit, 5000);
      expect(data.credits.single.amount, 5000);
      expect(data.overdueCount, 1);
      expect((await repo.getSyncStatus()).lastError, isNull);
    });

    test('parcourt toutes les pages', () async {
      goOnline((request) async {
        if (lastSegment(request.url) == 'customers') {
          final page = int.parse(request.url.queryParameters['page']!);
          final rows = page == 1
              ? [for (var i = 0; i < 100; i++) customerJson(i)]
              : [for (var i = 100; i < 105; i++) customerJson(i)];
          return jsonResponse({
            'customers': rows,
            'total': 105,
            'page': page,
            'page_size': 100,
          });
        }
        return FakeServer.healthy(request);
      });
      await repo.sync();
      expect((await repo.getCustomers()).length, 105);
    });

    test('ne télécharge pas tant qu\'il reste des éléments à envoyer',
        () async {
      await repo.createCustomer(name: 'Local');
      await settle();
      goOnline((request) async => request.method == 'POST'
          ? http.Response('', 503)
          : FakeServer.healthy(request));

      await repo.sync();

      expect(server.gets, isEmpty);
      expect((await repo.getCustomers()).single.name, 'Local');
    });

    test('un échec de lecture garde les données locales intactes', () async {
      await repo.createCustomer(name: 'Local');
      await settle();
      goOnline();
      await repo.sync(pull: false); // tout est parti
      server.handler = (request) async => request.method == 'GET'
          ? http.Response('', 500)
          : http.Response('', 201);

      await repo.sync();

      expect((await repo.getCustomers()).single.name, 'Local');
      expect((await repo.getSyncStatus()).lastError, isNotNull);
    });
  });

  group('migration v1 → v2', () {
    test('convertit les centimes en FCFA et met les anciens envois en erreur',
        () async {
      final old = await databaseFactoryFfi.openDatabase(
        inMemoryDatabasePath,
        options: OpenDatabaseOptions(
            version: 1, onCreate: _createV1, singleInstance: false),
      );

      await DatabaseHelper.migrate(old, 1, 2);

      final credit = (await old.query('credits')).single;
      expect(credit['amount'], 5000); // 500000 centimes -> 5 000 FCFA
      expect(credit['status'], 'pending'); // 'active' n'existe pas côté serveur
      expect(credit['description'], '');
      final payment = (await old.query('payments')).single;
      expect(payment['amount'], 2000);
      expect(payment['credit_id'], '');

      final queue = await old.query('sync_queue', orderBy: 'id');
      // L'ancien envoi en attente (format refusé par le serveur) devient
      // visible « en erreur » ; celui déjà envoyé reste tel quel.
      expect(queue[0]['synced'], SyncState.failed);
      expect(queue[0]['last_error'], contains('Ancien format'));
      expect(queue[1]['synced'], SyncState.synced);
      await old.close();
    });
  });

  group('lecture incrémentale', () {
    Map<String, dynamic> customerJson(String id, String updatedAt) => {
          'id': id,
          'name': 'Client $id',
          'phone': '',
          'address': '',
          'notes': '',
          'photo_path': '',
          'total_credit': '0',
          'total_paid': '0',
          'balance': '0',
          'is_active': true,
          'created_at': '2026-11-01T10:00:00',
          'updated_at': updatedAt,
          'sync_status': 'pending',
        };

    /// Serveur dont la liste des clients est fournie par [customers] ;
    /// crédits et paiements vides.
    Handler serverWith(List<Map<String, dynamic>> Function() customers) {
      return (request) async {
        if (request.method == 'GET' && lastSegment(request.url) == 'customers') {
          final rows = customers();
          return jsonResponse({
            'customers': rows,
            'total': rows.length,
            'page': 1,
            'page_size': 100,
          });
        }
        return FakeServer.healthy(request);
      };
    }

    String? sinceOf(String resource) => server.gets
        .where((r) => lastSegment(r.url) == resource)
        .last
        .url
        .queryParameters['updated_since'];

    test('premier téléchargement complet, les suivants demandent le delta',
        () async {
      goOnline(serverWith(() => [customerJson('c1', '2026-11-11T10:00:00')]));

      await repo.sync();
      expect(sinceOf('customers'), isNull); // rien en mémoire : tout

      server.requests.clear();
      await repo.sync();
      expect(sinceOf('customers'), '2026-11-11T10:00:00');
      // Pas de ligne vue pour les crédits : pas de curseur, on redemande tout
      // (c'est peu cher quand il n'y a rien).
      expect(sinceOf('credits'), isNull);
    });

    test('le delta s\'ajoute au local sans rien effacer ; le curseur avance',
        () async {
      var rows = [customerJson('c1', '2026-11-11T10:00:00')];
      goOnline(serverWith(() => rows));
      await repo.sync();

      rows = [customerJson('c2', '2026-11-12T08:30:00.250000+00:00')];
      server.requests.clear();
      await repo.sync();

      expect((await repo.getCustomers()).map((c) => c.id).toSet(), {'c1', 'c2'});

      server.requests.clear();
      await repo.sync();
      expect(sinceOf('customers'), '2026-11-12T08:30:00.250000+00:00');
    });

    test('un échec de lecture n\'avance pas le curseur', () async {
      goOnline(serverWith(() => [customerJson('c1', '2026-11-11T10:00:00')]));
      await repo.sync();

      server.handler = (request) async => http.Response('', 500);
      await repo.sync();

      goOnline(serverWith(() => []));
      await repo.sync();
      expect(sinceOf('customers'), '2026-11-11T10:00:00');
    });

    test('un enregistrement modifié pendant le téléchargement : on garde les '
        'données mais le curseur reste', () async {
      // Page 1 puis page 2 qui répète c0 : c0 a été modifié entre les deux
      // requêtes (il a changé de place dans le tri).
      goOnline((request) async {
        if (lastSegment(request.url) == 'customers') {
          final page = int.parse(request.url.queryParameters['page']!);
          final rows = page == 1
              ? [
                  for (var i = 0; i < 100; i++)
                    customerJson('c$i', '2026-11-11T10:00:00')
                ]
              : [customerJson('c0', '2026-11-11T10:05:00')];
          return jsonResponse({
            'customers': rows,
            'total': 101,
            'page': page,
            'page_size': 100,
          });
        }
        return FakeServer.healthy(request);
      });
      await repo.sync();
      expect((await repo.getCustomers()).length, 100);

      server.requests.clear();
      await repo.sync();
      expect(sinceOf('customers'), isNull); // pas de curseur : on recommence
    });

    test('la date est encodée dans l\'URL (le + du fuseau ne devient pas un '
        'espace)', () async {
      goOnline(serverWith(
          () => [customerJson('c1', '2026-11-11T10:00:00+00:00')]));
      await repo.sync();

      server.requests.clear();
      await repo.sync();

      final url = server.gets
          .firstWhere((r) => lastSegment(r.url) == 'customers')
          .url
          .toString();
      expect(url, contains('updated_since=2026-11-11T10%3A00%3A00%2B00%3A00'));
    });
  });

  group('migration v2 → v3', () {
    test('crée la table des curseurs sans toucher aux données', () async {
      final old = await databaseFactoryFfi.openDatabase(
        inMemoryDatabasePath,
        options: OpenDatabaseOptions(
            version: 1, onCreate: _createV1, singleInstance: false),
      );
      await DatabaseHelper.migrate(old, 1, DatabaseHelper.schemaVersion);

      await old.insert('sync_meta', {'key': 'cursor_customers', 'value': 'x'});
      expect((await old.query('sync_meta')).single['value'], 'x');
      expect((await old.query('credits')).single['amount'], 5000);
      await old.close();
    });
  });
}

/// Schéma et données tels que la version 1 de l'app les stockait.
Future<void> _createV1(Database db, int version) async {
  await db.execute('CREATE TABLE credits (id TEXT PRIMARY KEY, '
      'customer_id TEXT NOT NULL, amount INTEGER NOT NULL, '
      "status TEXT NOT NULL DEFAULT 'active', due_date TEXT, "
      'created_at TEXT NOT NULL)');
  await db.execute('CREATE TABLE payments (id TEXT PRIMARY KEY, '
      'customer_id TEXT NOT NULL, amount INTEGER NOT NULL, '
      "method TEXT NOT NULL DEFAULT 'cash', created_at TEXT NOT NULL)");
  await db.execute('CREATE TABLE sync_queue (id INTEGER PRIMARY KEY '
      'AUTOINCREMENT, table_name TEXT NOT NULL, record_id TEXT NOT NULL, '
      'action TEXT NOT NULL, payload TEXT NOT NULL, '
      'created_at TEXT NOT NULL, synced INTEGER NOT NULL DEFAULT 0)');
  await db.insert('credits', {
    'id': 'k1',
    'customer_id': 'c1',
    'amount': 500000, // 5 000 FCFA saisis, stockés x100
    'status': 'active',
    'created_at': '2026-01-01T00:00:00.000',
  });
  await db.insert('payments', {
    'id': 'p1',
    'customer_id': 'c1',
    'amount': 200000,
    'created_at': '2026-01-01T00:00:00.000',
  });
  for (final synced in [0, 1]) {
    await db.insert('sync_queue', {
      'table_name': 'credits',
      'record_id': 'k1',
      'action': 'insert',
      'payload': '{}',
      'created_at': '2026-01-01T00:00:00.000',
      'synced': synced,
    });
  }
}
