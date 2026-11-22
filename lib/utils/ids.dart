import 'dart:math';

final Random _random = Random.secure();

/// Identifiant unique (UUID v4) généré sur le téléphone.
///
/// Il est créé hors ligne puis envoyé tel quel au serveur : si la requête est
/// renvoyée après une coupure, le serveur reconnaît l'id et ne crée pas de
/// doublon (création idempotente).
String newId() {
  final bytes = List<int>.generate(16, (_) => _random.nextInt(256));
  bytes[6] = (bytes[6] & 0x0f) | 0x40; // version 4
  bytes[8] = (bytes[8] & 0x3f) | 0x80; // variante RFC 4122
  String hex(int from, int to) => bytes
      .sublist(from, to)
      .map((b) => b.toRadixString(16).padLeft(2, '0'))
      .join();
  return '${hex(0, 4)}-${hex(4, 6)}-${hex(6, 8)}-${hex(8, 10)}-${hex(10, 16)}';
}
