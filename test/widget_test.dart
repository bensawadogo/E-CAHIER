// Smoke test : l'app démarre sur une base vide, hors ligne, et affiche le
// tableau de bord puis les autres onglets sans erreur.

import 'dart:io';

import 'package:ecahier/database/database.dart';
import 'package:ecahier/main.dart';
import 'package:ecahier/repositories/ecahier_repository.dart';
import 'package:ecahier/services/api_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

/// Charge Roboto (la police réelle des téléphones Android) depuis le SDK
/// Flutter. Les tests utilisent sinon « Ahem », dont chaque lettre est un
/// carré aussi large que haut : environ deux fois plus large qu'un vrai texte,
/// ce qui ferait « déborder » des écrans parfaitement corrects.
Future<bool> loadRoboto() async {
  final root = Platform.environment['FLUTTER_ROOT'];
  if (root == null) return false;
  final loader = FontLoader('Roboto');
  var found = false;
  for (final name in ['regular', 'medium', 'bold']) {
    final file = File('$root/bin/cache/artifacts/material_fonts/roboto-$name.ttf');
    if (file.existsSync()) {
      final bytes = file.readAsBytesSync();
      loader.addFont(Future.value(ByteData.sublistView(Uint8List.fromList(bytes))));
      found = true;
    }
  }
  if (found) await loader.load();
  return found;
}

void main() {
  late Database db;

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
    // Téléphone sans réseau.
    EcahierRepository.instance = EcahierRepository(
      api: ApiService(
        client: MockClient(
            (_) async => throw const SocketException('pas de réseau')),
        baseUrl: 'http://test/api',
        authToken: '',
        retryDelay: Duration.zero,
      ),
    );
  });

  tearDown(() async {
    await db.close();
    DatabaseHelper.instance.useDatabase(null);
  });

  /// Laisse le vrai temps s'écouler (sqflite_ffi travaille dans un isolate)
  /// en redessinant jusqu'à ce que [finder] trouve quelque chose.
  Future<void> pumpUntilFound(WidgetTester tester, Finder finder) async {
    for (var i = 0; i < 100; i++) {
      // Fait aussi avancer l'horloge simulée (les réessais utilisent
      // Future.delayed, qui sinon ne se déclenche jamais dans un test).
      await tester.pump(const Duration(milliseconds: 100));
      if (finder.evaluate().isNotEmpty) return;
      await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 100)));
    }
    await tester.pump();
  }

  testWidgets('démarre hors ligne et navigue entre les onglets',
      (tester) async {
    await tester.pumpWidget(const EcahierApp());
    await pumpUntilFound(tester, find.text('Aucun client enregistré.'));

    expect(find.text('Tableau de bord'), findsOneWidget);
    expect(find.text('Aucun client enregistré.'), findsOneWidget);
    // Libellés de navigation toujours visibles (utilisateurs peu lecteurs).
    final nav = find.byType(NavigationBar);
    for (final label in ['Accueil', 'Clients', 'Crédits', 'Paiements', 'Sync']) {
      expect(find.descendant(of: nav, matching: find.text(label)),
          findsOneWidget);
    }

    await tester.tap(find.descendant(of: nav, matching: find.text('Clients')));
    await pumpUntilFound(tester, find.textContaining('Aucun client.'));
    expect(find.textContaining('Aucun client.'), findsOneWidget);

    await tester.tap(find.descendant(of: nav, matching: find.text('Sync')));
    await pumpUntilFound(tester, find.text('Synchroniser maintenant'));
    expect(find.text('Synchroniser maintenant'), findsOneWidget);
  });

  testWidgets('un client créé hors ligne apparaît tout de suite et signale '
      "l'élément en attente", (tester) async {
    await tester.pumpWidget(const EcahierApp());
    await pumpUntilFound(tester, find.text('Aucun client enregistré.'));

    await tester.runAsync(() => EcahierRepository.instance
        .createCustomer(name: 'Awa Ouédraogo', phone: '70000000'));
    await pumpUntilFound(tester, find.text('Awa Ouédraogo'));

    expect(find.text('Awa Ouédraogo'), findsOneWidget);
    expect(find.textContaining("en attente d'envoi"), findsOneWidget);
  });

  // Beaucoup d'utilisateurs agrandissent le texte du téléphone et ont un petit
  // écran : rien ne doit déborder (Flutter lève sinon « RenderFlex overflowed »).
  // Le scénario prépare un écran 360x640, des données réalistes (nom long, gros
  // montant), puis exécute [steps] en relevant chaque erreur de mise en page
  // avec l'écran et le widget fautifs.
  Future<void> runLargeText(
    WidgetTester tester,
    double scale,
    Future<void> Function(
      Future<void> Function() settle,
      void Function(String where) at,
    ) steps,
  ) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1.0;
    tester.platformDispatcher.textScaleFactorTestValue = scale;
    addTearDown(() {
      tester.view.resetPhysicalSize();
      tester.view.resetDevicePixelRatio();
      tester.platformDispatcher.clearAllTestValues();
    });

    final hasRoboto = await tester.runAsync(loadRoboto) ?? false;
    if (!hasRoboto) {
      markTestSkipped('Police Roboto introuvable dans le SDK Flutter : '
          'mesures de texte non fiables avec la police de test.');
      return;
    }

    await tester.runAsync(() async {
      final repo = EcahierRepository.instance;
      final customer = await repo.createCustomer(
          name: 'Aminata Ouédraogo-Compaoré', phone: '70 00 00 00');
      final credit = await repo.createCredit(
          customerId: customer.id,
          amount: 1250000,
          description: 'Riz, huile, sucre et savon pour le mois de décembre');
      await repo.createPayment(creditId: credit.id, amount: 250000);
    });

    await tester.pumpWidget(const EcahierApp());
    await pumpUntilFound(tester, find.textContaining('Aminata'));

    final problems = <String>[];
    var where = 'Accueil';
    final previous = FlutterError.onError;
    FlutterError.onError = (details) {
      final culprit = details
          .toString()
          .split(RegExp(r'[\r\n]+'))
          .where((l) => l.contains('/lib/'))
          .map((l) => l.trim().split('/lib/').last)
          .take(2)
          .join(' | ');
      problems.add(
          '[$where] ${details.exceptionAsString().split('\n').first} $culprit');
    };

    Future<void> settle() async {
      for (var i = 0; i < 6; i++) {
        await tester.pump(const Duration(milliseconds: 100));
        await tester.runAsync(
            () => Future<void>.delayed(const Duration(milliseconds: 50)));
      }
    }

    try {
      await steps(settle, (w) => where = w);
    } catch (e) {
      // Un débordement précédent peut laisser l'arbre de rendu dans un état où
      // les recherches échouent : on le note au lieu de masquer la cause.
      problems.add('[$where] erreur secondaire (${e.runtimeType})');
    } finally {
      FlutterError.onError = previous;
    }
    expect(problems.toSet(), isEmpty,
        reason: 'texte à ${(scale * 100).round()} %');
  }

  for (final scale in [1.0, 1.5, 2.0]) {
    testWidgets(
        'aucun onglet ne déborde à ${(scale * 100).round()} % de taille de '
        'texte (écran 360x640)', (tester) async {
      await runLargeText(tester, scale, (settle, at) async {
        final nav = find.byType(NavigationBar);
        for (final label in ['Accueil', 'Clients', 'Crédits', 'Paiements', 'Sync']) {
          at(label);
          await tester.tap(find.descendant(of: nav, matching: find.text(label)));
          await settle();
        }
      });
    });
  }

  // Les fenêtres de saisie sont celles où l'on tape au clavier, souvent avec
  // le texte agrandi : elles doivent s'ouvrir et se fermer sans déborder.
  for (final scale in [1.0, 2.0]) {
    testWidgets(
        'les formulaires de saisie ne débordent pas à '
        '${(scale * 100).round()} % de texte', (tester) async {
      await runLargeText(tester, scale, (settle, at) async {
        final nav = find.byType(NavigationBar);
        for (final (tab, tooltip) in [
          ('Clients', 'Nouveau client'),
          ('Crédits', 'Nouveau crédit'),
          ('Paiements', 'Nouveau paiement'),
        ]) {
          at(tooltip);
          await tester.tap(find.descendant(of: nav, matching: find.text(tab)));
          await settle();
          await tester.tap(find.byTooltip(tooltip));
          await settle();
          expect(find.byType(AlertDialog), findsOneWidget,
              reason: 'le formulaire « $tooltip » doit s\'ouvrir');
          Navigator.of(tester.element(find.byType(AlertDialog))).pop();
          await settle();
        }
      });
    });
  }
}
