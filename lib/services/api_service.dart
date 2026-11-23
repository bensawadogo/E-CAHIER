import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;

import '../models/credit.dart';
import '../models/customer.dart';
import '../models/payment.dart';

/// Durée maximale d'une requête. Courte : sur une connexion faible, mieux
/// vaut échouer vite et réessayer plus tard que bloquer la file d'envoi.
const Duration _defaultTimeout = Duration(seconds: 10);

/// Nombre de tentatives en cas d'erreur réseau, 5xx ou 429.
/// Sans danger pour les POST : les ids sont générés par l'app et le serveur
/// ignore un renvoi (création idempotente).
const int _maxAttempts = 2;

/// Taille des pages lues au serveur (petites pages = peu de données perdues
/// si la connexion saute).
const int _pageSize = 100;

// --- Production : lancer avec
//   --dart-define=CAHIER_API_BASE_URL=https://mon-serveur/api
//   --dart-define=CAHIER_AUTH_TOKEN=<même valeur que CAHIER_AUTH_TOKEN du serveur>
const String _envApiBaseUrl = String.fromEnvironment('CAHIER_API_BASE_URL');
const String _envAuthToken = String.fromEnvironment('CAHIER_AUTH_TOKEN');

/// Réponse HTTP en erreur.
class ApiException implements Exception {
  final int statusCode;
  final String message;

  const ApiException(this.statusCode, this.message);

  /// Jeton absent ou refusé : inutile de continuer, rien ne passera.
  bool get isAuthError => statusCode == 401 || statusCode == 403;

  /// Le serveur refuse la donnée elle-même (400, 404, 409, 422...). La
  /// renvoyer telle quelle échouera toujours : il ne faut pas boucler.
  /// 408 et 429 sont temporaires, donc exclus.
  bool get isPermanent =>
      statusCode >= 400 &&
      statusCode < 500 &&
      !isAuthError &&
      statusCode != 408 &&
      statusCode != 429;

  @override
  String toString() => 'HTTP $statusCode : $message';
}

class ApiService {
  /// URL de base de l'API. En Web, si aucune URL n'est fournie au build, on
  /// utilise l'origine du document courant (pas de souci CORS).
  static String get baseUrl {
    if (_envApiBaseUrl.isNotEmpty) return _envApiBaseUrl;
    if (kIsWeb) return '${Uri.base.origin}/api';
    return 'http://10.0.2.2:8000/api';
  }

  final http.Client _client;
  final String _baseUrl;
  final String _authToken;
  final Duration _retryDelay;
  final Duration _timeout;

  ApiService({
    http.Client? client,
    String? baseUrl,
    String? authToken,
    Duration retryDelay = const Duration(seconds: 1),
    Duration timeout = _defaultTimeout,
  })  : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? ApiService.baseUrl,
        _authToken = authToken ?? _envAuthToken,
        _retryDelay = retryDelay,
        _timeout = timeout;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        if (_authToken.isNotEmpty) 'Authorization': 'Bearer $_authToken',
      };

  /// Envoie une requête, avec timeout court et une nouvelle tentative sur
  /// les erreurs temporaires. Lève [ApiException] si le serveur répond par un
  /// code d'erreur, ou l'erreur réseau d'origine si aucune réponse n'arrive.
  Future<http.Response> _send(
    String method,
    String path, {
    Object? body,
    Duration? timeout,
  }) async {
    timeout ??= _timeout;
    final uri = Uri.parse('$_baseUrl$path');
    Object? lastError;

    for (var attempt = 1; attempt <= _maxAttempts; attempt++) {
      try {
        final http.Response response;
        if (method == 'GET') {
          response =
              await _client.get(uri, headers: _headers).timeout(timeout);
        } else {
          response = await _client
              .post(uri, headers: _headers, body: json.encode(body))
              .timeout(timeout);
        }

        if (response.statusCode >= 200 && response.statusCode < 300) {
          return response;
        }
        final error = ApiException(response.statusCode, _detail(response));
        if (error.isAuthError || error.isPermanent) throw error;
        lastError = error; // 5xx, 429, 408 : on retente
      } on ApiException {
        rethrow;
      } catch (e) {
        lastError = e; // timeout, coupure réseau
      }
      if (attempt < _maxAttempts) {
        await Future<void>.delayed(_retryDelay * attempt);
      }
    }
    throw lastError ?? StateError('Requête impossible');
  }

  /// Message d'erreur du serveur (`{"detail": ...}`) sans planter si le
  /// corps n'est pas du JSON.
  String _detail(http.Response response) {
    try {
      final decoded = json.decode(utf8.decode(response.bodyBytes));
      if (decoded is Map && decoded['detail'] != null) {
        return decoded['detail'].toString();
      }
    } catch (_) {}
    return response.reasonPhrase ?? 'Erreur';
  }

  /// Envoie une création (`POST /customers/`, `/credits/`, `/payments/`).
  Future<void> post(String resource, Map<String, dynamic> body) async {
    await _send('POST', '/$resource/', body: body);
  }

  /// Lit les pages d'une ressource. Le serveur renvoie
  /// `{<clé>: [...], total, page, page_size}`, pas une liste nue.
  ///
  /// Avec [updatedSince] (lecture incrémentale), seuls les enregistrements
  /// modifiés depuis cette date reviennent, triés par date de modification.
  Future<Pulled<T>> _getAll<T>(
    String resource,
    T Function(Map<String, dynamic>) parse, {
    String? updatedSince,
  }) async {
    final since = updatedSince == null
        ? ''
        : '&updated_since=${Uri.encodeQueryComponent(updatedSince)}';
    final items = <T>[];
    final seenIds = <Object?>{};
    String? newest;
    var consistent = true;
    var page = 1;
    while (true) {
      final response = await _send(
          'GET', '/$resource/?page=$page&page_size=$_pageSize$since');
      final decoded = json.decode(utf8.decode(response.bodyBytes));
      final rows = (decoded is Map ? decoded[resource] : decoded) as List?;
      if (rows == null || rows.isEmpty) break;
      for (final row in rows.cast<Map<String, dynamic>>()) {
        // Un id vu deux fois = un enregistrement modifié PENDANT le
        // téléchargement : il a changé de place dans le tri et un voisin a pu
        // être sauté. On garde les données mais on n'avance pas le curseur :
        // le prochain téléchargement rattrape tout.
        if (!seenIds.add(row['id'])) consistent = false;
        final changed = row['updated_at'];
        if (changed is String && (newest == null || changed.compareTo(newest) > 0)) {
          newest = changed;
        }
        items.add(parse(row));
      }
      final total = decoded is Map ? decoded['total'] as int? : null;
      if (total == null || items.length >= total || rows.length < _pageSize) {
        break;
      }
      page++;
      if (page > 500) break; // garde-fou contre une boucle infinie
    }
    return Pulled(items, consistent ? newest : null);
  }

  Future<Pulled<Customer>> getCustomers({String? updatedSince}) =>
      _getAll('customers', Customer.fromJson, updatedSince: updatedSince);

  Future<Pulled<Credit>> getCredits({String? updatedSince}) =>
      _getAll('credits', Credit.fromJson, updatedSince: updatedSince);

  Future<Pulled<Payment>> getPayments({String? updatedSince}) =>
      _getAll('payments', Payment.fromJson, updatedSince: updatedSince);
}

/// Résultat d'un téléchargement : les éléments et le nouveau curseur (la plus
/// récente date de modification vue), ou `null` s'il ne faut pas l'avancer.
class Pulled<T> {
  final List<T> items;
  final String? cursor;
  const Pulled(this.items, this.cursor);
}
