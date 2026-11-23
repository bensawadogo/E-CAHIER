import 'package:flutter/material.dart';

import '../repositories/ecahier_repository.dart';
import 'ecahier_widgets.dart';

/// Charge des données locales et se redessine quand elles changent.
///
/// Remplace les `FutureBuilder` répétés dans chaque écran :
/// - le chargement n'est lancé qu'une fois (et non à chaque `build`) ;
/// - pendant un rechargement, les anciennes données restent affichées (pas de
///   spinner qui clignote après une écriture ou une synchro) ;
/// - une réponse lente ne peut pas écraser une plus récente.
class RepoBuilder<T> extends StatefulWidget {
  const RepoBuilder({
    super.key,
    required this.load,
    required this.builder,
    this.repository,
    this.refreshOn = const [],
    this.loading,
    this.error,
  });

  final Future<T> Function(EcahierRepository repo) load;
  final Widget Function(BuildContext context, T data) builder;

  /// Repository à utiliser (par défaut l'instance partagée).
  final EcahierRepository? repository;

  /// Notifiers supplémentaires qui déclenchent un rechargement.
  final List<Listenable> refreshOn;

  /// Affichage pendant le premier chargement (spinner par défaut).
  final Widget? loading;

  /// Affichage si la lecture échoue avant tout chargement (message + bouton
  /// « Réessayer » par défaut).
  final Widget? error;

  @override
  State<RepoBuilder<T>> createState() => _RepoBuilderState<T>();
}

class _RepoBuilderState<T> extends State<RepoBuilder<T>> {
  late final EcahierRepository _repo =
      widget.repository ?? EcahierRepository.instance;
  late final Listenable _merged =
      Listenable.merge([_repo, ...widget.refreshOn]);

  T? _data;
  bool _hasData = false;
  Object? _error;
  int _request = 0;

  @override
  void initState() {
    super.initState();
    _merged.addListener(_reload);
    _reload();
  }

  @override
  void dispose() {
    _merged.removeListener(_reload);
    super.dispose();
  }

  Future<void> _reload() async {
    final request = ++_request;
    try {
      final data = await widget.load(_repo);
      if (!mounted || request != _request) return;
      setState(() {
        _data = data;
        _hasData = true;
        _error = null;
      });
    } catch (e) {
      if (!mounted || request != _request) return;
      setState(() => _error = e);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_hasData) return widget.builder(context, _data as T);
    if (_error != null) {
      return widget.error ??
          ErrorState(
            message: 'Impossible de lire les données de ce téléphone.',
            onRetry: _reload,
          );
    }
    return widget.loading ??
        const Center(child: CircularProgressIndicator());
  }
}
