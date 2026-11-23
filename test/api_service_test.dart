// Tests unitaires d'ApiService avec un client HTTP SIMULÉ (mocktail) : aucun
// réseau, aucune base. On vérifie ce que l'app envoie (en-têtes, URL, corps)
// et comment elle réagit à chaque type de réponse (réessai, refus définitif,
// jeton refusé, coupure, délai dépassé).

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:ecahier/services/api_service.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:mocktail/mocktail.dart';

class MockClient extends Mock implements http.Client {}

http.Response json200(Object body, [int status = 200]) => http.Response(
    json.encode(body), status,
    headers: {'content-type': 'application/json; charset=utf-8'});

void main() {
  late MockClient client;

  setUpAll(() {
    registerFallbackValue(Uri());
  });

  setUp(() => client = MockClient());

  ApiService api({
    String token = '',
    Duration timeout = const Duration(seconds: 5),
  }) =>
      ApiService(
        client: client,
        baseUrl: 'http://test/api',
        authToken: token,
        retryDelay: Duration.zero,
        timeout: timeout,
      );

  void stubPost(Future<http.Response> Function() answer) {
    when(() => client.post(any(),
        headers: any(named: 'headers'),
        body: any(named: 'body'))).thenAnswer((_) => answer());
  }

  void stubGet(Future<http.Response> Function(Uri uri) answer) {
    when(() => client.get(any(), headers: any(named: 'headers')))
        .thenAnswer((i) => answer(i.positionalArguments.first as Uri));
  }

  int postCalls() => verify(() => client.post(any(),
      headers: any(named: 'headers'), body: any(named: 'body'))).callCount;

  group('POST (envoi d\'une création)', () {
    test('envoie URL, corps JSON et jeton Bearer', () async {
      stubPost(() async => json200({}, 201));

      await api(token: 'secret').post('customers', {'id': 'c1', 'name': 'Awa'});

      final captured = verify(() => client.post(
            captureAny(),
            headers: captureAny(named: 'headers'),
            body: captureAny(named: 'body'),
          )).captured;
      expect(captured[0].toString(), 'http://test/api/customers/');
      final headers = captured[1] as Map<String, String>;
      expect(headers['Authorization'], 'Bearer secret');
      expect(headers['Content-Type'], 'application/json');
      expect(json.decode(captured[2] as String), {'id': 'c1', 'name': 'Awa'});
    });

    test('sans jeton configuré, aucun en-tête Authorization', () async {
      stubPost(() async => json200({}, 201));

      await api().post('customers', {});

      final headers = verify(() => client.post(any(),
              headers: captureAny(named: 'headers'),
              body: any(named: 'body')))
          .captured
          .single as Map<String, String>;
      expect(headers.containsKey('Authorization'), isFalse);
    });

    test('422 : refus définitif, une seule tentative', () async {
      stubPost(() async => json200({'detail': 'Nom invalide'}, 422));

      final error = await api()
          .post('customers', {})
          .then<ApiException?>((_) => null)
          .catchError((Object e) => e as ApiException);

      expect(error!.statusCode, 422);
      expect(error.isPermanent, isTrue);
      expect(error.isAuthError, isFalse);
      expect(error.message, 'Nom invalide');
      expect(postCalls(), 1);
    });

    for (final code in [401, 403]) {
      test('$code : jeton refusé, une seule tentative', () async {
        stubPost(() async => json200({'detail': 'Unauthorized'}, code));

        await expectLater(
          api().post('customers', {}),
          throwsA(isA<ApiException>()
              .having((e) => e.isAuthError, 'isAuthError', true)
              .having((e) => e.isPermanent, 'isPermanent', false)),
        );
        expect(postCalls(), 1);
      });
    }

    test('503 puis 201 : une nouvelle tentative réussit', () async {
      final answers = [
        http.Response('', 503),
        json200({}, 201),
      ];
      stubPost(() async => answers.removeAt(0));

      await api().post('customers', {});

      expect(postCalls(), 2);
    });

    for (final code in [429, 408]) {
      test('$code est temporaire : on réessaie', () async {
        final answers = [http.Response('', code), json200({}, 201)];
        stubPost(() async => answers.removeAt(0));

        await api().post('customers', {});

        expect(postCalls(), 2);
      });
    }

    test('503 deux fois : abandon après 2 tentatives, erreur serveur', () async {
      stubPost(() async => http.Response('', 503));

      await expectLater(
        api().post('customers', {}),
        throwsA(isA<ApiException>()
            .having((e) => e.statusCode, 'statusCode', 503)
            .having((e) => e.isPermanent, 'isPermanent', false)),
      );
      expect(postCalls(), 2);
    });

    test('coupure réseau : l\'erreur d\'origine est relancée après 2 essais',
        () async {
      stubPost(() async => throw const SocketException('pas de réseau'));

      await expectLater(
          api().post('customers', {}), throwsA(isA<SocketException>()));
      expect(postCalls(), 2);
    });

    test('délai dépassé : TimeoutException, sans bloquer', () async {
      stubPost(() => Completer<http.Response>().future); // ne répond jamais

      await expectLater(
        api(timeout: const Duration(milliseconds: 30)).post('customers', {}),
        throwsA(isA<TimeoutException>()),
      );
      expect(postCalls(), 2);
    });

    test('corps d\'erreur qui n\'est pas du JSON : message de repli', () async {
      stubPost(() async => http.Response('<html>oups</html>', 400,
          reasonPhrase: 'Bad Request'));

      await expectLater(
        api().post('customers', {}),
        throwsA(isA<ApiException>()
            .having((e) => e.message, 'message', 'Bad Request')),
      );
    });
  });

  group('GET (lecture paginée)', () {
    Map<String, dynamic> row(int i, {String? updatedAt}) => {
          'id': 'c$i',
          'name': 'Client $i',
          'created_at': '2026-11-01T10:00:00',
          'updated_at': updatedAt ?? '2026-11-0${(i % 9) + 1}T10:00:00',
          'is_active': true,
          'total_credit': '0',
          'total_paid': '0',
        };

    test('parcourt les pages jusqu\'au total', () async {
      stubGet((uri) async {
        final page = int.parse(uri.queryParameters['page']!);
        final rows = page == 1
            ? [for (var i = 0; i < 100; i++) row(i)]
            : [for (var i = 100; i < 105; i++) row(i)];
        return json200({'customers': rows, 'total': 105});
      });

      final result = await api().getCustomers();

      expect(result.items, hasLength(105));
      final urls = verify(() => client.get(captureAny(),
              headers: any(named: 'headers')))
          .captured
          .map((u) => (u as Uri).queryParameters['page'])
          .toList();
      expect(urls, ['1', '2']);
    });

    test('accepte aussi une liste nue (ancien format)', () async {
      stubGet((_) async => json200([row(1), row(2)]));

      final result = await api().getCustomers();

      expect(result.items.map((c) => c.id), ['c1', 'c2']);
    });

    test('updated_since est encodé : le + du fuseau n\'devient pas un espace',
        () async {
      stubGet((_) async => json200({'customers': [], 'total': 0}));

      await api().getCustomers(updatedSince: '2026-11-11T10:00:00+00:00');

      final uri = verify(() => client.get(captureAny(),
              headers: any(named: 'headers')))
          .captured
          .single as Uri;
      expect(uri.toString(), contains('%2B00%3A00'));
      expect(uri.queryParameters['updated_since'],
          '2026-11-11T10:00:00+00:00');
    });

    test('le curseur est la date de modification la plus récente', () async {
      stubGet((_) async => json200({
            'customers': [
              row(1, updatedAt: '2026-11-05T10:00:00+00:00'),
              row(2, updatedAt: '2026-11-09T08:30:00+00:00'),
              row(3, updatedAt: '2026-11-07T23:59:59+00:00'),
            ],
            'total': 3,
          }));

      final result = await api().getCustomers();

      expect(result.cursor, '2026-11-09T08:30:00+00:00');
    });

    test('réponse vide : pas de curseur', () async {
      stubGet((_) async => json200({'customers': [], 'total': 0}));

      final result = await api().getCustomers(updatedSince: 'x');

      expect(result.items, isEmpty);
      expect(result.cursor, isNull);
    });

    test('un id vu deux fois (modifié pendant le téléchargement) : '
        'données gardées, curseur retenu', () async {
      stubGet((uri) async {
        final page = int.parse(uri.queryParameters['page']!);
        final rows = page == 1
            ? [for (var i = 0; i < 100; i++) row(i)]
            : [row(0, updatedAt: '2026-11-09T09:00:00')];
        return json200({'customers': rows, 'total': 101});
      });

      final result = await api().getCustomers();

      expect(result.items, hasLength(101));
      expect(result.cursor, isNull);
    });

    test('une page en erreur 500 fait échouer la lecture entière', () async {
      var calls = 0;
      stubGet((_) async {
        calls++;
        return calls == 1
            ? json200({
                'customers': [for (var i = 0; i < 100; i++) row(i)],
                'total': 150,
              })
            : http.Response('', 500);
      });

      await expectLater(api().getCustomers(), throwsA(isA<ApiException>()));
    });

    test('crédits et paiements utilisent leurs propres ressources', () async {
      stubGet((uri) async {
        final resource = uri.pathSegments.where((s) => s.isNotEmpty).last;
        return json200({resource: [], 'total': 0});
      });

      await api().getCredits();
      await api().getPayments();

      final paths = verify(() => client.get(captureAny(),
              headers: any(named: 'headers')))
          .captured
          .map((u) => (u as Uri).path)
          .toList();
      expect(paths, ['/api/credits/', '/api/payments/']);
    });
  });

  group('ApiException', () {
    test('classement des codes HTTP', () {
      bool permanent(int c) => ApiException(c, '').isPermanent;
      expect([400, 404, 409, 422].every(permanent), isTrue);
      expect([401, 403, 408, 429, 500, 502, 503].any(permanent), isFalse);
      expect(const ApiException(401, '').isAuthError, isTrue);
      expect(const ApiException(403, '').isAuthError, isTrue);
      expect(const ApiException(404, '').isAuthError, isFalse);
      expect(const ApiException(422, 'x').toString(), 'HTTP 422 : x');
    });
  });
}
