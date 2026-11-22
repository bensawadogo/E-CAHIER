// Contrat avec le serveur : formats réels renvoyés par l'API FastAPI
// (Decimal en chaînes, dates sans fuseau) et formatage FCFA.

import 'package:ecahier/models/credit.dart';
import 'package:ecahier/models/customer.dart';
import 'package:ecahier/models/payment.dart';
import 'package:ecahier/utils/ids.dart';
import 'package:ecahier/utils/parsing.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('parseAmount', () {
    test('accepte les Decimal sérialisés en chaînes par le serveur', () {
      expect(parseAmount('5000'), 5000);
      expect(parseAmount('0.0'), 0);
      expect(parseAmount('1500.50'), 1501);
    });

    test('accepte entiers, décimaux et null', () {
      expect(parseAmount(5000), 5000);
      expect(parseAmount(5000.4), 5000);
      expect(parseAmount(null), 0);
      expect(parseAmount('abc'), 0);
    });
  });

  group('parseAmountInput', () {
    test('lit les saisies courantes', () {
      expect(parseAmountInput('5000'), 5000);
      expect(parseAmountInput('5 000'), 5000);
      expect(parseAmountInput('5.000'), 5000);
      expect(parseAmountInput('5,000'), 5000);
    });

    test('rejette vide, zéro, négatif et texte (sans planter)', () {
      expect(parseAmountInput(''), isNull);
      expect(parseAmountInput('0'), isNull);
      expect(parseAmountInput('-5'), isNull);
      expect(parseAmountInput('abc'), isNull);
    });
  });

  group('formatCurrency', () {
    test('sépare les milliers et ne divise pas par 100', () {
      expect(formatCurrency(5000), '5 000 FCFA');
      expect(formatCurrency(1250000), '1 250 000 FCFA');
      expect(formatCurrency(0), '0 FCFA');
      expect(formatCurrency(999), '999 FCFA');
    });
  });

  group('parseServerDate', () {
    test('une date sans fuseau est de l\'UTC', () {
      final d = parseServerDate('2026-11-11T10:00:00');
      expect(d.isUtc, isTrue);
      expect(d.hour, 10);
    });

    test('respecte Z et les décalages', () {
      expect(parseServerDate('2026-11-11T10:00:00Z').hour, 10);
      expect(parseServerDate('2026-11-11T10:00:00+02:00').hour, 8);
    });

    test('valeur absente ou illisible : ne plante pas', () {
      expect(parseServerDate(null).isUtc, isTrue);
      expect(parseServerDate('n\'importe quoi').isUtc, isTrue);
    });
  });

  group('modèles ↔ JSON du serveur', () {
    test('Customer.fromJson lit les totaux en chaînes', () {
      final c = Customer.fromJson({
        'id': 'c1',
        'name': 'Awa',
        'phone': '70000000',
        'address': '',
        'notes': '',
        'total_credit': '5000',
        'total_paid': '0.0',
        'is_active': true,
        'created_at': '2026-11-11T10:00:00',
      });
      expect(c.totalCredit, 5000);
      expect(c.totalPaid, 0);
    });

    test('Credit.fromJson : statut serveur et montant en FCFA', () {
      final c = Credit.fromJson({
        'id': 'k1',
        'customer_id': 'c1',
        'amount': '5000',
        'status': 'partial',
        'due_date': '2020-01-01T00:00:00Z',
        'created_at': '2019-12-01T00:00:00Z',
      });
      expect(c.amount, 5000);
      expect(c.isOpen, isTrue);
      expect(c.isOverdue(), isTrue);
    });

    test('un crédit payé n\'est jamais en retard', () {
      final c = Credit(
        id: 'k',
        customerId: 'c',
        amount: 1,
        status: CreditStatus.paid,
        dueDate: DateTime.utc(2020),
        createdAt: DateTime.utc(2019),
      );
      expect(c.isOverdue(), isFalse);
    });

    test('Payment.fromJson lit credit_id et payment_date', () {
      final p = Payment.fromJson({
        'id': 'p1',
        'customer_id': 'c1',
        'credit_id': 'k1',
        'amount': '2000',
        'method': 'mobile_money',
        'payment_date': '2026-11-11T10:00:00Z',
        'created_at': '2026-11-11T11:00:00Z',
      });
      expect(p.creditId, 'k1');
      expect(p.amount, 2000);
      expect(p.createdAt.hour, 10);
    });

    test('les corps de création contiennent l\'id et les champs exigés', () {
      final now = DateTime.utc(2026);
      expect(
        Customer(id: 'c1', name: 'Awa', createdAt: now).toApiJson(),
        {'id': 'c1', 'name': 'Awa', 'phone': '', 'address': '', 'notes': ''},
      );
      expect(
        Payment(
          id: 'p1',
          customerId: 'c1',
          creditId: 'k1',
          amount: 2000,
          createdAt: now,
        ).toApiJson(),
        {
          'id': 'p1',
          'customer_id': 'c1',
          'credit_id': 'k1',
          'amount': 2000,
          'method': 'cash',
        },
      );
    });
  });

  group('newId', () {
    test('produit des UUID v4 uniques acceptés par le serveur', () {
      final ids = {for (var i = 0; i < 500; i++) newId()};
      expect(ids.length, 500);
      final uuid = RegExp(
          r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$');
      expect(ids.every(uuid.hasMatch), isTrue);
      // même motif que la validation du serveur
      expect(ids.every(RegExp(r'^[A-Za-z0-9_-]{1,64}$').hasMatch), isTrue);
    });
  });
}
