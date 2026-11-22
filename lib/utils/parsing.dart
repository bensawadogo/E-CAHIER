/// Conversions tolérantes pour les JSON du serveur, et formatage FCFA/dates.
library;

/// Convertit un montant JSON en FCFA entiers.
///
/// Le serveur sérialise les `Decimal` en chaînes (`"5000"`, `"0.0"`) ; un
/// simple `as int` planterait. Le FCFA n'a pas de centimes : on arrondit.
int parseAmount(Object? value) {
  if (value == null) return 0;
  if (value is int) return value;
  if (value is num) return value.round();
  return (num.tryParse(value.toString()) ?? 0).round();
}

final RegExp _hasZone = RegExp(r'(Z|[+-]\d{2}:?\d{2})$');

/// Lit une date du serveur et la renvoie en UTC.
///
/// Une date sans fuseau est considérée comme UTC (c'est ce que le serveur
/// écrit), pas comme heure locale du téléphone.
DateTime parseServerDate(Object? value) {
  if (value is! String || value.isEmpty) return DateTime.now().toUtc();
  final text =
      value.contains('T') && !_hasZone.hasMatch(value) ? '${value}Z' : value;
  return (DateTime.tryParse(text) ?? DateTime.now()).toUtc();
}

/// Date lisible `jj/mm/aaaa` en heure locale.
String formatDate(DateTime date) {
  final d = date.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${two(d.day)}/${two(d.month)}/${d.year}';
}

/// Montant FCFA avec séparateur de milliers : `5 000 FCFA`.
String formatCurrency(int fcfa) {
  final digits = fcfa.abs().toString();
  final buffer = StringBuffer();
  for (var i = 0; i < digits.length; i++) {
    if (i > 0 && (digits.length - i) % 3 == 0) buffer.write(' ');
    buffer.write(digits[i]);
  }
  final sign = fcfa < 0 ? '-' : '';
  return '$sign$buffer FCFA';
}

/// Lit un montant saisi au clavier (`5000`, `5 000`, `5.000`, `5,000`).
/// Renvoie `null` si ce n'est pas un entier strictement positif.
int? parseAmountInput(String text) {
  final cleaned = text.replaceAll(RegExp(r'[\s., ]'), '');
  final value = int.tryParse(cleaned);
  return (value == null || value <= 0) ? null : value;
}
