import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:http/http.dart' as http;
import '../models/customer.dart';
import '../models/credit.dart';
import '../models/payment.dart';

// Production : lancer avec --dart-define=CAHIER_API_BASE_URL=https://mon-serveur/api
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

  Future<List<Customer>> getCustomers() async {
    final response = await http.get(Uri.parse('$baseUrl/customers/'));
    if (response.statusCode == 200) {
      List<dynamic> data = json.decode(response.body);
      return data.map((json) => Customer.fromJson(json)).toList();
    }
    throw Exception('Failed to load customers');
  }

  Future<List<Credit>> getCredits() async {
    final response = await http.get(Uri.parse('$baseUrl/credits/'));
    if (response.statusCode == 200) {
      List<dynamic> data = json.decode(response.body);
      return data.map((json) => Credit.fromJson(json)).toList();
    }
    throw Exception('Failed to load credits');
  }

  Future<List<Payment>> getPayments() async {
    final response = await http.get(Uri.parse('$baseUrl/payments/'));
    if (response.statusCode == 200) {
      List<dynamic> data = json.decode(response.body);
      return data.map((json) => Payment.fromJson(json)).toList();
    }
    throw Exception('Failed to load payments');
  }

  Future<Customer> createCustomer(Customer customer) async {
    final response = await http.post(
      Uri.parse('$baseUrl/customers/'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode(customer.toJson()),
    );
    if (response.statusCode == 200 || response.statusCode == 201) {
      return Customer.fromJson(json.decode(response.body));
    }
    throw Exception('Failed to create customer');
  }

  Future<Credit> createCredit(Credit credit) async {
    final response = await http.post(
      Uri.parse('$baseUrl/credits/'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode(credit.toJson()),
    );
    if (response.statusCode == 200 || response.statusCode == 201) {
      return Credit.fromJson(json.decode(response.body));
    }
    throw Exception('Failed to create credit');
  }

  Future<Payment> createPayment(Payment payment) async {
    final response = await http.post(
      Uri.parse('$baseUrl/payments/'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode(payment.toJson()),
    );
    if (response.statusCode == 200 || response.statusCode == 201) {
      return Payment.fromJson(json.decode(response.body));
    }
    throw Exception('Failed to create payment');
  }
}
