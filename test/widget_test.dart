// Smoke test : l'application Ecahier se construit et affiche le dashboard.

import 'package:flutter_test/flutter_test.dart';

import 'package:ecahier/main.dart';

void main() {
  testWidgets("L'app se lance et affiche son titre", (WidgetTester tester) async {
    await tester.pumpWidget(const EcahierApp());
    expect(find.text('Ecahier'), findsWidgets);
  });
}
