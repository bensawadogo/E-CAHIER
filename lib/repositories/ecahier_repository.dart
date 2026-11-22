import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:sqflite/sqflite.dart';

import '../database/credit_dao.dart';
import '../database/customer_dao.dart';
import '../database/database.dart';
import '../database/payment_dao.dart';
import '../database/sync_meta_dao.dart';
import '../database/sync_queue_dao.dart';
import '../models/credit.dart';
import '../models/customer.dart';
import '../models/payment.dart';
import '../services/api_service.dart';
import '../utils/ids.dart';
import '../utils/parsing.dart';

/// Erreur métier lisible par l'utilisateur (message déjà en français).
class RepositoryException implements Exception {
  final String message;
  const RepositoryException(this.message);

  @override
  String toString() => message;
}

/// Toutes les données locales, lues d'un coup.
class Snapshot {
  final List<Customer> customers;
  final List<Credit> credits;
  final List<Payment> payments;

  Snapshot(this.customers, this.credits, this.payments);

  late final Map<String, Customer> customersById = {
    for (final c in customers) c.id: c,
  };

  late final Map<String, int> _paidByCredit = () {
    final totals = <String, int>{};
    for (final p in payments) {
      totals[p.creditId] = (totals[p.creditId] ?? 0) + p.amount;
    }
    return totals;
  }();

  Customer customerOf(String id) => customersById[id] ?? Customer.unknown();

  /// Reste à payer sur un crédit.
  int remaining(Credit credit) {
    final left = credit.amount - (_paidByCredit[credit.id] ?? 0);
    return left < 0 ? 0 : left;
  }

  int get overdueCount => credits.where((c) => c.isOverdue()).length;
}

/// Où en est la synchronisation.
class SyncStatus {
  final int pending;
  final int failed;
  final bool syncing;
  final DateTime? lastSyncAt;
  final String? lastError;
  final List<SyncEntry> failedEntries;

  const SyncStatus({
    required this.pending,
    required this.failed,
    required this.syncing,
    this.lastSyncAt,
    this.lastError,
    this.failedEntries = const [],
  });
}

/// Repository offline-first.
///
/// - **Lecture** : toujours depuis SQLite, instantanée, sans réseau.
/// - **Écriture** : SQLite + file d'envoi dans UNE transaction, puis envoi au
///   serveur en arrière-plan. L'écran n'attend jamais le réseau.
/// - **Sync** : envoi des entrées en attente (ordre de création), puis
///   récupération des données du serveur. Chaque entrée est idempotente (id
///   généré sur le téléphone), donc un renvoi ne crée jamais de doublon.
///
/// Les écrans écoutent ce [ChangeNotifier] pour se rafraîchir.
class EcahierRepository extends ChangeNotifier {
  /// Instance partagée par toute l'application (une seule file, une seule
  /// synchro à la fois).
  static EcahierRepository instance = EcahierRepository();

  /// Délai maximal entre deux récupérations complètes depuis le serveur
  /// quand la synchro est déclenchée par une écriture (économise la data).
  static const Duration _minPullInterval = Duration(minutes: 5);

  final ApiService _api;
  final CustomerDao _customerDao;
  final CreditDao _creditDao;
  final PaymentDao _paymentDao;
  final SyncQueueDao _syncDao;
  final SyncMetaDao _metaDao;

  /// `true` pendant une synchronisation (pour l'écran Sync). Séparé de
  /// [notifyListeners], qui signifie « les données ont changé ».
  final ValueNotifier<bool> syncing = ValueNotifier(false);
  Future<void>? _running;
  bool _runAgain = false;
  bool _wantPull = false;
  DateTime? _lastSyncAt;
  DateTime? _lastPullAt;
  String? _lastError;

  EcahierRepository({
    ApiService? api,
    CustomerDao? customerDao,
    CreditDao? creditDao,
    PaymentDao? paymentDao,
    SyncQueueDao? syncDao,
    SyncMetaDao? metaDao,
  })  : _api = api ?? ApiService(),
        _customerDao = customerDao ?? CustomerDao(),
        _creditDao = creditDao ?? CreditDao(),
        _paymentDao = paymentDao ?? PaymentDao(),
        _syncDao = syncDao ?? SyncQueueDao(),
        _metaDao = metaDao ?? SyncMetaDao();

  // -----------------------------------------------------------------
  // LECTURE : toujours locale
  // -----------------------------------------------------------------

  Future<Snapshot> loadSnapshot() async {
    final results = await Future.wait([
      _customerDao.getAll(),
      _creditDao.getAll(),
      _paymentDao.getAll(),
    ]);
    return Snapshot(
      results[0] as List<Customer>,
      results[1] as List<Credit>,
      results[2] as List<Payment>,
    );
  }

  Future<List<Customer>> getCustomers() => _customerDao.getAll();
  Future<List<Credit>> getCredits() => _creditDao.getAll();
  Future<List<Payment>> getPayments() => _paymentDao.getAll();

  Future<int> pendingCount() => _syncDao.count(SyncState.pending);

  Future<SyncStatus> getSyncStatus() async {
    final failedEntries = await _syncDao.getFailed();
    return SyncStatus(
      pending: await _syncDao.count(SyncState.pending),
      failed: failedEntries.length,
      syncing: syncing.value,
      lastSyncAt: _lastSyncAt,
      lastError: _lastError,
      failedEntries: failedEntries,
    );
  }

  // -----------------------------------------------------------------
  // ÉCRITURE : SQLite + file d'envoi (une transaction), puis envoi en
  // arrière-plan
  // -----------------------------------------------------------------

  Future<Customer> createCustomer({
    required String name,
    String? phone,
    String? address,
    String? notes,
  }) async {
    final cleanName = name.trim();
    if (cleanName.isEmpty) {
      throw const RepositoryException('Le nom du client est obligatoire.');
    }
    final customer = Customer(
      id: newId(),
      name: cleanName,
      phone: phone?.trim(),
      address: address?.trim(),
      notes: notes?.trim(),
      createdAt: DateTime.now().toUtc(),
    );
    await _write((txn) async {
      await _customerDao.insert(customer, executor: txn);
      await _enqueue(txn, 'customers', customer.id, customer.toApiJson());
    });
    return customer;
  }

  Future<Credit> createCredit({
    required String customerId,
    required int amount,
    String description = '',
    DateTime? dueDate,
  }) async {
    if (amount <= 0) {
      throw const RepositoryException('Le montant doit être supérieur à 0.');
    }
    final now = DateTime.now().toUtc();
    final credit = Credit(
      id: newId(),
      customerId: customerId,
      amount: amount,
      description: description.trim(),
      // Même règle que le serveur : 30 jours par défaut.
      dueDate: (dueDate ?? now.add(const Duration(days: 30))).toUtc(),
      createdAt: now,
    );
    await _write((txn) async {
      await _creditDao.insert(credit, executor: txn);
      await _enqueue(txn, 'credits', credit.id, credit.toApiJson());
    });
    return credit;
  }

  Future<Payment> createPayment({
    required String creditId,
    required int amount,
    String method = 'cash',
  }) async {
    if (amount <= 0) {
      throw const RepositoryException('Le montant doit être supérieur à 0.');
    }
    late Payment payment;
    await _write((txn) async {
      final credit = await _creditDao.getById(creditId, executor: txn);
      if (credit == null) {
        throw const RepositoryException('Crédit introuvable.');
      }
      final alreadyPaid =
          await _paymentDao.totalForCredit(creditId, executor: txn);
      final remaining = credit.amount - alreadyPaid;
      if (!credit.isOpen || remaining <= 0) {
        throw const RepositoryException('Ce crédit est déjà soldé.');
      }
      if (amount > remaining) {
        throw RepositoryException(
            'Le montant dépasse le reste à payer (${formatCurrency(remaining)}).');
      }
      payment = Payment(
        id: newId(),
        customerId: credit.customerId,
        creditId: creditId,
        amount: amount,
        method: method,
        createdAt: DateTime.now().toUtc(),
      );
      await _paymentDao.insert(payment, executor: txn);
      await _creditDao.updateStatus(
        creditId,
        amount == remaining ? CreditStatus.paid : CreditStatus.partial,
        executor: txn,
      );
      await _enqueue(txn, 'payments', payment.id, payment.toApiJson());
    });
    return payment;
  }

  Future<void> _write(Future<void> Function(Transaction txn) action) async {
    final db = await DatabaseHelper.instance.database;
    await db.transaction(action);
    notifyListeners();
    // Envoi en arrière-plan : on n'attend pas le réseau. Sans « pull » ici
    // (voir _minPullInterval) pour ménager la connexion.
    unawaited(sync(pull: false));
  }

  Future<void> _enqueue(Transaction txn, String table, String recordId,
      Map<String, dynamic> payload) {
    return _syncDao.insert(
      SyncEntry(
        tableName: table,
        recordId: recordId,
        action: 'insert',
        payload: json.encode(payload),
        createdAt: DateTime.now().toUtc(),
      ),
      executor: txn,
    );
  }

  // -----------------------------------------------------------------
  // SYNCHRONISATION
  // -----------------------------------------------------------------

  /// Envoie les entrées en attente puis, si [pull], récupère les données du
  /// serveur. Ne lève jamais d'exception.
  ///
  /// Si une synchro est déjà en cours, on ne lance pas une deuxième en
  /// parallèle : on attend la fin de celle-ci (elle repartira une fois si une
  /// écriture ou une demande de lecture est arrivée entre-temps).
  Future<void> sync({bool pull = true}) {
    _wantPull = _wantPull || pull;
    final running = _running;
    if (running != null) {
      _runAgain = true;
      return running;
    }
    return _running = _runSyncLoop().whenComplete(() => _running = null);
  }

  Future<void> _runSyncLoop() async {
    syncing.value = true;
    try {
      var ok = true;
      // On repart si une écriture est arrivée pendant l'envoi, sauf si le
      // réseau vient d'échouer (inutile de marteler une connexion coupée).
      do {
        _runAgain = false;
        final wantPull = _wantPull;
        _wantPull = false;
        ok = await _syncOnce(pull: wantPull);
      } while (_runAgain && ok);
    } catch (_) {
      // Une synchro ne doit jamais faire planter l'app (disque plein,
      // base verrouillée...) : on garde les données et on réessaiera.
      _lastError = 'Erreur inattendue pendant la synchronisation.';
    } finally {
      syncing.value = false;
      notifyListeners();
    }
  }

  /// Remet les entrées refusées en attente et relance l'envoi.
  Future<void> retryFailed() async {
    await _syncDao.retryFailed();
    notifyListeners();
    await sync(pull: false);
  }

  /// Renvoie `false` si l'envoi a été interrompu (réseau, jeton).
  Future<bool> _syncOnce({required bool pull}) async {
    final pushed = await _push();
    if (!pushed) return false;
    final due = _lastPullAt == null ||
        DateTime.now().difference(_lastPullAt!) > _minPullInterval;
    // On ne télécharge que si la file est vide : les données du serveur
    // écraseraient sinon des lignes locales (ex. statut d'un crédit) dont le
    // paiement n'est pas encore parti.
    if ((pull || due) && await _syncDao.count(SyncState.pending) == 0) {
      await _pull();
    }
    return true;
  }

  /// Envoie la file. Renvoie `false` si l'envoi a été interrompu (réseau
  /// coupé, jeton refusé) : on réessaiera plus tard.
  Future<bool> _push() async {
    final pending = await _syncDao.getPending();
    var ok = true;
    for (final entry in pending) {
      try {
        await _api.post(
            entry.tableName, json.decode(entry.payload) as Map<String, dynamic>);
        await _syncDao.markSynced(entry.id!);
      } on ApiException catch (e) {
        if (e.isAuthError) {
          _lastError = 'Accès refusé par le serveur (jeton invalide).';
          ok = false;
          break;
        }
        if (e.isPermanent) {
          // Donnée refusée : on la garde visible, on passe à la suivante.
          await _syncDao.markFailed(entry.id!, e.message);
          continue;
        }
        _lastError = 'Serveur indisponible, nouvel essai plus tard.';
        ok = false;
        break;
      } catch (_) {
        _lastError = 'Pas de connexion, nouvel essai plus tard.';
        ok = false;
        break;
      }
    }
    await _syncDao.deleteAllSynced();
    if (ok) {
      _lastError = null;
      _lastSyncAt = DateTime.now();
    }
    return ok;
  }

  Future<void> _pull() async {
    try {
      // Pas de lecture entre les deux : tout est téléchargé AVANT d'écrire,
      // puis écrit en une transaction (jamais de base à moitié à jour).
      // Lecture incrémentale : on ne redemande que ce qui a changé depuis le
      // dernier téléchargement réussi (premier lancement : tout).
      final customers = await _api.getCustomers(
          updatedSince: await _metaDao.get(SyncMetaDao.cursorKey('customers')));
      final credits = await _api.getCredits(
          updatedSince: await _metaDao.get(SyncMetaDao.cursorKey('credits')));
      final payments = await _api.getPayments(
          updatedSince: await _metaDao.get(SyncMetaDao.cursorKey('payments')));
      final db = await DatabaseHelper.instance.database;
      await db.transaction((txn) async {
        await _customerDao.upsertAll(customers.items, executor: txn);
        await _creditDao.upsertAll(credits.items, executor: txn);
        await _paymentDao.upsertAll(payments.items, executor: txn);
        // Curseurs écrits dans la MÊME transaction que les données : jamais un
        // curseur avancé sans les lignes correspondantes.
        for (final (resource, cursor) in [
          ('customers', customers.cursor),
          ('credits', credits.cursor),
          ('payments', payments.cursor),
        ]) {
          if (cursor != null) {
            await _metaDao.set(SyncMetaDao.cursorKey(resource), cursor,
                executor: txn);
          }
        }
      });
      _lastPullAt = DateTime.now();
      _lastSyncAt = _lastPullAt;
      _lastError = null;
    } on ApiException catch (e) {
      _lastError = e.isAuthError
          ? 'Accès refusé par le serveur (jeton invalide).'
          : 'Impossible de récupérer les données du serveur.';
    } catch (_) {
      _lastError = 'Pas de connexion, données du serveur non mises à jour.';
    }
  }
}
