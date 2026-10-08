import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;
import '../models/customer.dart';
import '../models/credit.dart';
import '../models/payment.dart';

// Duration maximale d'une requête HTTP.
const Duration _defaultTimeout = Duration(seconds: 12);

// Nombre maximal de tentatives en cas d'erreur (5xx, 429, timeout).
const int _maxRetries = 3;

// --- Production : lancer avec --dart-define=CAHIER_API_BASE_URL=https://mon-serveur/api
const String _envApiBaseUrl = String.fromEnvironment('CAHIER_API_BASE_URL');

class ApiService {
  /// URL de base de l'API. En Web (Flutter build web), si une URL explicite
  /// est fournie au build (--dart-define), elle est prioritaire ; sinon on
  /// utilise l'origine du document courant pour éviter les problèmes CORS.
  static String get baseUrl {
    if (_envApiBaseUrl.isNotEmpty) {
      return _envApiBaseUrl;
    }
    if (kIsWeb) {
      final origin = Uri.base.origin; // ex: http://localhost:8000
      return '$origin/api';
    }
    return 'http://10.0.2.2:8000/api';
  }

  final http.Client _client;

  ApiService([http.Client? client]) : _client = client ?? http.Client();

  /// Enveloppe HTTP publique avec timeout et retries exponentiels.
  /// Retry sur les erreurs serveur (5xx), 429 Too Many Requests, et timeouts.
  Future<http.Response> request(
    String method,
    String url, {
    Map<String, String>? headers,
    Object? body,
    Duration timeout = _defaultTimeout,
  }) async {
    final uri = Uri.parse(url);
    int attempt = 0;
    Object? lastError;

    while (attempt < _maxRetries) {
      try {
        final response = await _httpMethod(method, uri, headers, body)
            .timeout(timeout);

        if (_shouldRetry(response.statusCode)) {
          lastError = Exception(
              'Retryable status ${response.statusCode}');
          attempt++;
          if (attempt < _maxRetries) {
            await _backoff(attempt);
          }
          continue;
        }
        return response;
      } on TimeoutException catch (e) {
        lastError = e;
        attempt++;
        if (attempt < _maxRetries) {
          await _backoff(attempt);
        }
      } catch (e) {
        lastError = e;
        attempt++;
        if (attempt < _maxRetries) {
          await _backoff(attempt);
        }
      }
    }

    throw lastError ?? Exception('Max retries exceeded');
  }

  Future<http.Response> _httpMethod(
    String method,
    Uri uri,
    Map<String, String>? headers,
    Object? body,
  ) {
    final h = headers ?? {'Content-Type': 'application/json'};
    final encodedBody = body is Map<String, dynamic>
        ? json.encode(body)
        : body is String
            ? body
            : null;

    switch (method) {
      case 'GET':
        return _client.get(uri, headers: h);
      case 'POST':
        return _client.post(uri, headers: h, body: encodedBody);
      case 'PUT':
        return _client.put(uri, headers: h, body: encodedBody);
      case 'DELETE':
        return _client.delete(uri, headers: h, body: encodedBody);
      default:
        throw UnsupportedError('Unsupported HTTP method: $method');
    }
  }

  /// Détermine si le code de statut HTTP nécessite une nouvelle tentative.
  bool _shouldRetry(int statusCode) {
    return statusCode == 429 ||
        (statusCode >= 500 && statusCode < 600);
  }

  /// Backoff exponentiel : 2s, 4s entre les tentatives.
  Future<void> _backoff(int attempt) {
    final delay = Duration(seconds: 2 * attempt);
    return Future.delayed(delay);
  }

  Future<List<Customer>> getCustomers() async {
    final response = await request('GET', '$baseUrl/customers/');
    if (response.statusCode == 200) {
      List<dynamic> data = json.decode(response.body);
      return data.map((json) => Customer.fromJson(json)).toList();
    }
    throw Exception('Failed to load customers');
  }

  Future<List<Credit>> getCredits() async {
    final response = await request('GET', '$baseUrl/credits/');
    if (response.statusCode == 200) {
      List<dynamic> data = json.decode(response.body);
      return data.map((json) => Credit.fromJson(json)).toList();
    }
    throw Exception('Failed to load credits');
  }

  Future<List<Payment>> getPayments() async {
    final response = await request('GET', '$baseUrl/payments/');
    if (response.statusCode == 200) {
      List<dynamic> data = json.decode(response.body);
      return data.map((json) => Payment.fromJson(json)).toList();
    }
    throw Exception('Failed to load payments');
  }

  Future<Customer> createCustomer(Customer customer) async {
    final response = await request(
      'POST',
      '$baseUrl/customers/',
      body: customer.toJson(),
    );
    if (response.statusCode == 200 || response.statusCode == 201) {
      return Customer.fromJson(json.decode(response.body));
    }
    throw Exception('Failed to create customer');
  }

  Future<Credit> createCredit(Credit credit) async {
    final response = await request(
      'POST',
      '$baseUrl/credits/',
      body: credit.toJson(),
    );
    if (response.statusCode == 200 || response.statusCode == 201) {
      return Credit.fromJson(json.decode(response.body));
    }
    throw Exception('Failed to create credit');
  }

  Future<Payment> createPayment(Payment payment) async {
    final response = await request(
      'POST',
      '$baseUrl/payments/',
      body: payment.toJson(),
    );
    if (response.statusCode == 200 || response.statusCode == 201) {
      return Payment.fromJson(json.decode(response.body));
    }
    throw Exception('Failed to create payment');
  }
}
