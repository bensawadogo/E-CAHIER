import 'dart:convert';
import '../models/customer.dart';
import '../models/credit.dart';
import '../models/payment.dart';
import '../database/customer_dao.dart';
import '../database/credit_dao.dart';
import '../database/payment_dao.dart';
import '../database/sync_queue_dao.dart';
import '../services/api_service.dart';

/// Repository offline-first : tente l'API en premier, bascule sur SQLite
/// en cas d'échec. Les nouvelles entrées sont écrites localement puis
/// mise en file d'attente pour synchronisation ultérieure.
class EcahierRepository {
  final ApiService _api;
  final CustomerDao _customerDao;
  final CreditDao _creditDao;
  final PaymentDao _paymentDao;
  final SyncQueueDao _syncDao;

  EcahierRepository({
    ApiService? api,
    CustomerDao? customerDao,
    CreditDao? creditDao,
    PaymentDao? paymentDao,
    SyncQueueDao? syncDao,
  })  : _api = api ?? ApiService(),
        _customerDao = customerDao ?? CustomerDao(),
        _creditDao = creditDao ?? CreditDao(),
        _paymentDao = paymentDao ?? PaymentDao(),
        _syncDao = syncDao ?? SyncQueueDao();

  // -----------------------------------------------------------------
  // READ : API first, fallback to SQLite
  // -----------------------------------------------------------------

  Future<List<Customer>> getCustomers() async {
    try {
      final customers = await _api.getCustomers();
      for (final c in customers) {
        await _customerDao.upsert(c);
      }
      return customers;
    } catch (_) {
      return _customerDao.getAll();
    }
  }

  Future<List<Credit>> getCredits() async {
    try {
      final credits = await _api.getCredits();
      for (final c in credits) {
        await _creditDao.upsert(c);
      }
      return credits;
    } catch (_) {
      return _creditDao.getAll();
    }
  }

  Future<List<Payment>> getPayments() async {
    try {
      final payments = await _api.getPayments();
      for (final p in payments) {
        await _paymentDao.upsert(p);
      }
      return payments;
    } catch (_) {
      return _paymentDao.getAll();
    }
  }

  // -----------------------------------------------------------------
  // CREATE : write to SQLite + enqueue for sync
  // -----------------------------------------------------------------

  Future<Customer> createCustomer(Customer customer) async {
    await _customerDao.insert(customer);
    await _syncDao.insert(SyncEntry(
      tableName: 'customers',
      recordId: customer.id,
      action: 'insert',
      payload: json.encode(customer.toJson()),
      createdAt: DateTime.now(),
    ));
    try {
      return await _api.createCustomer(customer);
    } catch (_) {
      return customer;
    }
  }

  Future<Credit> createCredit(Credit credit) async {
    await _creditDao.insert(credit);
    await _syncDao.insert(SyncEntry(
      tableName: 'credits',
      recordId: credit.id,
      action: 'insert',
      payload: json.encode(credit.toJson()),
      createdAt: DateTime.now(),
    ));
    try {
      return await _api.createCredit(credit);
    } catch (_) {
      return credit;
    }
  }

  Future<Payment> createPayment(Payment payment) async {
    await _paymentDao.insert(payment);
    await _syncDao.insert(SyncEntry(
      tableName: 'payments',
      recordId: payment.id,
      action: 'insert',
      payload: json.encode(payment.toJson()),
      createdAt: DateTime.now(),
    ));
    try {
      return await _api.createPayment(payment);
    } catch (_) {
      return payment;
    }
  }

  // -----------------------------------------------------------------
  // SYNC : envoyer les entrées en attente vers l'API
  // -----------------------------------------------------------------

  Future<void> syncPending() async {
    final pending = await _syncDao.getPending();
    for (final entry in pending) {
      try {
        await _api.request('POST', '${ApiService.baseUrl}/${entry.tableName}/',
            body: json.decode(entry.payload));
        await _syncDao.markSynced(entry.id!);
      } catch (_) {
        // Laisse l'entrée en file pour une prochaine tentative.
      }
    }
  }
}
