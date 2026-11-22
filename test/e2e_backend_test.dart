// Test de bout en bout : le repository de l'app contre le VRAI backend
// FastAPI (formats JSON réels, jeton Bearer, création idempotente).
//
// Ignoré par défaut. Pour l'exécuter :
//   1. lancer le backend avec CAHIER_AUTH_TOKEN=e2e-token
//      (ex. python -m uvicorn backend.app.main:app --port 8765)
//   2. E2E_API=http://127.0.0.1:8765/api flutter test test/e2e_backend_test.dart
//
// Les tests reconnaissent leurs données par id : ils fonctionnent aussi sur
// un serveur qui contient déjà d'autres enregistrements.

import 'dart:convert';
import 'dart:io';

import 'package:ecahier/database/database.dart';
import 'package:ecahier/database/sync_meta_dao.dart';
import 'package:ecahier/models/credit.dart';
import 'package:ecahier/repositories/ecahier_repository.dart';
import 'package:ecahier/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

const _token = 'e2e-token';

void main() {
  final api = Platform.environment['E2E_API'];
  final skip = api == null ? 'Définir E2E_API pour lancer ce test' : null;

  Database? db;

  setUpAll(() {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  });

  /// Une « installation » de l'app : sa propre base locale vide.
  Future<EcahierRepository> newPhone({String token = _token}) async {
    await db?.close();
    db = await databaseFactoryFfi.openDatabase(
      inMemoryDatabasePath,
      options: OpenDatabaseOptions(
        version: DatabaseHelper.schemaVersion,
        onCreate: DatabaseHelper.createSchema,
        singleInstance: false,
      ),
    );
    DatabaseHelper.instance.useDatabase(db);
    return EcahierRepository(
      api: ApiService(
          baseUrl: api, authToken: token, retryDelay: Duration.zero),
    );
  }

  tearDown(() async {
    await db?.close();
    db = null;
    DatabaseHelper.instance.useDatabase(null);
  });

  Future<dynamic> getJson(String path) async {
    final response = await http.get(Uri.parse('$api$path'),
        headers: {'Authorization': 'Bearer $_token'});
    expect(response.statusCode, 200, reason: path);
    return json.decode(response.body);
  }

  /// Le serveur sérialise les Decimal en chaînes ("2000.0") : on compare en
  /// nombre.
  double number(Object? value) => double.parse(value.toString());

  Future<List<dynamic>> listWithId(String resource, String id) async {
    final body = await getJson('/$resource/?page_size=200') as Map;
    return (body[resource] as List).where((r) => r['id'] == id).toList();
  }

  Future<double> totalPaid(String customerId) async =>
      number((await getJson('/customers/$customerId'))['total_paid']);

  test('client + crédit + paiement saisis hors ligne arrivent sans doublon',
      skip: skip, () async {
    final phone = await newPhone();
    final customer = await phone.createCustomer(name: 'Awa', phone: '70000000');
    final credit =
        await phone.createCredit(customerId: customer.id, amount: 5000);
    final payment = await phone.createPayment(creditId: credit.id, amount: 2000);

    await phone.sync();

    // Côté serveur : mêmes ids, montants en FCFA (pas x100), paiement lié.
    expect(await listWithId('customers', customer.id), hasLength(1));
    final serverCredit = (await listWithId('credits', credit.id)).single;
    expect(number(serverCredit['amount']), 5000);
    expect(serverCredit['status'], 'partial');
    expect(serverCredit['customer_id'], customer.id);
    final serverPayment = (await listWithId('payments', payment.id)).single;
    expect(serverPayment['credit_id'], credit.id);
    expect(await totalPaid(customer.id), 2000);

    expect(await phone.pendingCount(), 0);
    expect((await phone.getSyncStatus()).failed, 0);

    // Un renvoi du même paiement (coupure juste après l'envoi) ne le compte
    // pas deux fois.
    final resend = await http.post(
      Uri.parse('$api/payments/'),
      headers: {
        'Authorization': 'Bearer $_token',
        'Content-Type': 'application/json',
      },
      body: json.encode(payment.toApiJson()),
    );
    expect(resend.statusCode, 201);
    expect(await listWithId('payments', payment.id), hasLength(1));
    expect(await totalPaid(customer.id), 2000);
  });

  test('un autre téléphone récupère les données du serveur', skip: skip,
      () async {
    final first = await newPhone();
    final customer = await first.createCustomer(name: 'Moussa');
    final credit =
        await first.createCredit(customerId: customer.id, amount: 8000);
    final payment = await first.createPayment(creditId: credit.id, amount: 3000);
    await first.sync();

    final second = await newPhone(); // réinstallation : base vide
    expect((await second.loadSnapshot()).customers, isEmpty);
    await second.sync();

    final data = await second.loadSnapshot();
    expect(data.customersById.containsKey(customer.id), isTrue);
    final pulled = data.credits.firstWhere((c) => c.id == credit.id);
    // Statut venu du serveur ('partial'), reconnu par l'app ; montants en FCFA.
    expect(pulled.status, CreditStatus.partial);
    expect(pulled.amount, 8000);
    expect(data.remaining(pulled), 5000);
    final pulledPayment = data.payments.firstWhere((p) => p.id == payment.id);
    expect(pulledPayment.creditId, credit.id);
    expect(pulledPayment.amount, 3000);
  });

  test('lecture incrémentale : le vrai serveur comprend le curseur de l\'app',
      skip: skip, () async {
    final first = await newPhone();
    final old = await first.createCustomer(name: 'Très ancien');
    await first.sync();
    await Future<void>.delayed(const Duration(milliseconds: 20));
    await first.createCustomer(name: 'Avant');
    await first.sync();

    final second = await newPhone(); // autre téléphone, base vide
    await second.sync(); // téléchargement complet
    final cursor = await SyncMetaDao().get(SyncMetaDao.cursorKey('customers'));
    expect(cursor, isNotNull);

    await Future<void>.delayed(const Duration(milliseconds: 20));
    // Un troisième téléphone crée un client après le curseur.
    final writer = await newPhone();
    final b = await writer.createCustomer(name: 'Après');
    await writer.sync();

    final client = ApiService(baseUrl: api, authToken: _token);
    final delta = await client.getCustomers(updatedSince: cursor);
    final ids = delta.items.map((c) => c.id).toList();
    expect(ids, contains(b.id));
    expect(ids, isNot(contains(old.id)),
        reason: 'un client plus ancien que le curseur ne doit pas revenir');
    expect(delta.cursor, isNotNull);
  });

  test('un jeton refusé ne perd rien et le dit', skip: skip, () async {
    final phone = await newPhone(token: 'mauvais-jeton');
    await phone.createCustomer(name: 'Zoé');

    await phone.sync();

    final status = await phone.getSyncStatus();
    expect(status.pending, 1);
    expect(status.failed, 0);
    expect(status.lastError, contains('Accès refusé'));
  });
}
