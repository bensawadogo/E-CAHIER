// Test d'écran avec un repository SIMULÉ (mocktail) : pas de base, pas de
// réseau. On vérifie ce que l'utilisateur voit selon l'état de la
// synchronisation, et que ses gestes (Réessayer, Synchroniser maintenant)
// appellent bien le repository.

import 'package:ecahier/database/sync_queue_dao.dart';
import 'package:ecahier/repositories/ecahier_repository.dart';
import 'package:ecahier/screens/sync_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

class MockRepository extends Mock implements EcahierRepository {}

SyncEntry failedEntry(String table, String error) => SyncEntry(
      id: 1,
      tableName: table,
      recordId: 'x',
      action: 'insert',
      payload: '{}',
      createdAt: DateTime.utc(2026, 11, 1),
      state: SyncState.failed,
      lastError: error,
    );

void main() {
  late MockRepository repo;
  late ValueNotifier<bool> syncing;
  late EcahierRepository previous;

  setUp(() {
    previous = EcahierRepository.instance;
    repo = MockRepository();
    syncing = ValueNotifier(false);
    // EcahierRepository est un ChangeNotifier : l'écran s'y abonne.
    when(() => repo.addListener(any())).thenReturn(null);
    when(() => repo.removeListener(any())).thenReturn(null);
    when(() => repo.syncing).thenReturn(syncing);
    when(() => repo.loadSnapshot())
        .thenAnswer((_) async => Snapshot([], [], []));
    when(() => repo.sync()).thenAnswer((_) async {});
    when(() => repo.retryFailed()).thenAnswer((_) async {});
    EcahierRepository.instance = repo;
  });

  tearDown(() {
    EcahierRepository.instance = previous;
    syncing.dispose();
  });

  void stubStatus(SyncStatus status) =>
      when(() => repo.getSyncStatus()).thenAnswer((_) async => status);

  Future<void> show(WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: SyncScreen()));
    await tester.pump();
    await tester.pump();
  }

  testWidgets('tout est à jour : « Rien » à envoyer, aucune erreur',
      (tester) async {
    stubStatus(const SyncStatus(pending: 0, failed: 0, syncing: false));

    await show(tester);

    expect(find.text('Rien'), findsOneWidget);
    expect(find.text('Pas encore'), findsOneWidget);
    expect(find.text('Non envoyés'), findsNothing);
  });

  testWidgets('affiche le nombre d\'éléments en attente', (tester) async {
    stubStatus(const SyncStatus(pending: 3, failed: 0, syncing: false));

    await show(tester);

    expect(find.text('3'), findsOneWidget);
    expect(find.text('Rien'), findsNothing);
  });

  testWidgets('affiche la dernière erreur de connexion', (tester) async {
    stubStatus(const SyncStatus(
      pending: 1,
      failed: 0,
      syncing: false,
      lastError: 'Pas de connexion, nouvel essai plus tard.',
    ));

    await show(tester);

    expect(find.text('Pas de connexion, nouvel essai plus tard.'),
        findsOneWidget);
  });

  testWidgets('les éléments refusés sont listés avec leur motif',
      (tester) async {
    stubStatus(SyncStatus(
      pending: 0,
      failed: 2,
      syncing: false,
      failedEntries: [
        failedEntry('customers', 'Nom invalide'),
        failedEntry('payments', 'Ce crédit n\'appartient pas à ce client.'),
      ],
    ));

    await show(tester);

    expect(find.text('Non envoyés'), findsOneWidget);
    expect(find.text('Client : Nom invalide'), findsOneWidget);
    expect(find.textContaining('Paiement : Ce crédit'), findsOneWidget);
    expect(find.text('Refusés par le serveur'), findsOneWidget);
  });

  testWidgets('« Réessayer » relance les éléments refusés', (tester) async {
    stubStatus(SyncStatus(
      pending: 0,
      failed: 1,
      syncing: false,
      failedEntries: [failedEntry('customers', 'Nom invalide')],
    ));
    await show(tester);

    await tester.ensureVisible(find.text('Réessayer'));
    await tester.tap(find.text('Réessayer'));
    await tester.pump();

    verify(() => repo.retryFailed()).called(1);
  });

  testWidgets('« Synchroniser maintenant » lance une synchro et confirme',
      (tester) async {
    stubStatus(const SyncStatus(pending: 0, failed: 0, syncing: false));
    await show(tester);

    await tester.ensureVisible(find.text('Synchroniser maintenant'));
    await tester.tap(find.text('Synchroniser maintenant'));
    await tester.pump();
    await tester.pump();

    verify(() => repo.sync()).called(1);
    expect(find.text('Tout est à jour'), findsOneWidget);
  });

  testWidgets('si la synchro échoue, le message d\'erreur est montré',
      (tester) async {
    stubStatus(const SyncStatus(
      pending: 2,
      failed: 0,
      syncing: false,
      lastError: 'Accès refusé par le serveur (jeton invalide).',
    ));
    await show(tester);

    await tester.ensureVisible(find.text('Synchroniser maintenant'));
    await tester.tap(find.text('Synchroniser maintenant'));
    await tester.pump();
    await tester.pump();

    // Dans la page ET dans la notification.
    expect(find.text('Accès refusé par le serveur (jeton invalide).'),
        findsNWidgets(2));
  });

  testWidgets('pendant une synchro, le bouton est désactivé', (tester) async {
    stubStatus(const SyncStatus(pending: 1, failed: 0, syncing: true));
    syncing.value = true;
    await show(tester);

    expect(find.text('Synchronisation...'), findsOneWidget);
    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    expect(button.onPressed, isNull);
  });
}
