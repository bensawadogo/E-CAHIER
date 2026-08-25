/// Thème moderne et épuré pour l'application Ecahier.
/// Palette : teal professionnel avec accents violets et ambrés.
library;

import 'package:flutter/material.dart';

/// Palette de couleurs Ecahier — design moderne et épuré.
class AppColors {
  /// Couleur primaire — teal profond, professionnel et rassurant.
  static const Color primary = Color(0xFF0E7490);

  /// Couleur secondaire — violet doux pour les accents.
  static const Color secondary = Color(0xFF7C3AED);

  /// Couleur tertiaire — ambre pour les alertes et crédits.
  static const Color tertiary = Color(0xFFF59E0B);

  /// Couleur d'erreur.
  static const Color error = Color(0xFFDC2626);

  /// Couleurs de surface.
  static const Color surface = Color(0xFFF8FAFC);
  static const Color surfaceContainerLow = Colors.white;
  static const Color surfaceContainer = Color(0xFFF1F5F9);
  static const Color surfaceContainerHigh = Color(0xFFE2E8F0);

  /// Couleurs de texte.
  static const Color onSurface = Color(0xFF0F172A);
  static const Color onSurfaceVariant = Color(0xFF64748B);

  /// Thème clair Ecahier — moderne, épuré, Material 3.
class AppTheme {
  static ThemeData get light => ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: AppColors.primary,
          brightness: Brightness.light,
          primary: AppColors.primary,
          secondary: AppColors.secondary,
          tertiary: AppColors.tertiary,
          error: AppColors.error,
          surface: AppColors.surface,
          surfaceContainerLow: AppColors.surfaceContainerLow,
          surfaceContainer: AppColors.surfaceContainer,
          surfaceContainerHigh: AppColors.surfaceContainerHigh,
          surfaceContainerHighest: AppColors.surfaceContainerHigh,
          onSurface: AppColors.onSurface,
          onSurfaceVariant: AppColors.onSurfaceVariant,
        ),

        /// --- Typographie ---
        textTheme: const TextTheme(
          headlineLarge: TextStyle(
              fontSize: 28, fontWeight: FontWeight.w700, height: 1.2),
          headlineMedium: TextStyle(
              fontSize: 22, fontWeight: FontWeight.w600, height: 1.3),
          headlineSmall: TextStyle(
              fontSize: 18, fontWeight: FontWeight.w600, height: 1.3),
          titleLarge: TextStyle(
              fontSize: 18, fontWeight: FontWeight.w600, height: 1.3),
          titleMedium: TextStyle(
              fontSize: 16, fontWeight: FontWeight.w500, height: 1.4),
          titleSmall: TextStyle(
              fontSize: 14, fontWeight: FontWeight.w500, height: 1.4),
          bodyLarge: TextStyle(fontSize: 15, height: 1.5),
          bodyMedium: TextStyle(fontSize: 14, height: 1.5),
          bodySmall: TextStyle(fontSize: 12, height: 1.4),
          labelLarge: TextStyle(
              fontSize: 15, fontWeight: FontWeight.w600, height: 1.2),
        ),

                /// --- Scaffold ---
        scaffoldBackgroundColor: AppColors.surface,

        /// --- AppBar (propre, transparent) ---
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.transparent,
          foregroundColor: AppColors.onSurface,
          centerTitle: false,
          scrolledUnderBackgroundColor: Colors.transparent,
          elevation: 0,
          titleTextStyle: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w700,
            color: AppColors.onSurface,
          ),
        ),

        /// --- NavigationBar moderne ---
        navigationBarTheme: NavigationBarThemeData(
          backgroundColor: AppColors.surfaceContainerLow,
          elevation: 0,
          indicatorColor: AppColors.primary.withOpacity(0.12),
          labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
          labelTextStyle: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.selected)
                ? const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppColors.primary)
                : const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                    color: AppColors.onSurfaceVariant),
          ),
          iconTheme: WidgetStateProperty.resolveWith(
            (states) => states.contains(WidgetState.selected)
                ? const IconThemeData(
                    color: AppColors.primary, size: 24)
                : const IconThemeData(
                    color: AppColors.onSurfaceVariant, size: 22),
          ),
        ),

        /// --- Cartes ---
        cardTheme: CardThemeData(
          elevation: 0,
          shape: RoundedRectangleBorder(
              borderRadius:
                  BorderRadius.circular(AppColors.borderRadius)),
          color: AppColors.surfaceContainerLow,
          margin: EdgeInsets.zero,
        ),

        /// --- Entrées de formulaire ---
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(
            borderRadius:
                BorderRadius.circular(AppColors.buttonRadius),
            borderSide: BorderSide.none,
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius:
                BorderRadius.circular(AppColors.buttonRadius),
            borderSide: const BorderSide(color: Colors.transparent),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius:
                BorderRadius.circular(AppColors.buttonRadius),
            borderSide:
                const BorderSide(color: AppColors.primary, width: 2),
          ),
          errorBorder: OutlineInputBorder(
            borderRadius:
                BorderRadius.circular(AppColors.buttonRadius),
            borderSide:
                const BorderSide(color: AppColors.error, width: 2),
          ),
          filled: true,
          fillColor: AppColors.surfaceContainer,
          hintStyle: const TextStyle(color: Color(0xFF94A3B8)),
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        ),

        /// --- Boutons ---
        filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
            backgroundColor: AppColors.primary,
            foregroundColor: Colors.white,
            shape: RoundedRectangleBorder(
                borderRadius:
                    BorderRadius.circular(AppColors.buttonRadius)),
            textStyle: const TextStyle(
                fontSize: 15, fontWeight: FontWeight.w600),
          ),
        ),

        /// --- FAB ---
        floatingActionButtonTheme: FloatingActionButtonThemeData(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          elevation: 4,
          shape: RoundedRectangleBorder(
              borderRadius:
                  BorderRadius.circular(AppColors.borderRadius)),
        ),

        /// --- SnackBar ---
        snackBarTheme: SnackBarThemeData(
          backgroundColor: AppColors.onSurface,
          contentTextStyle: const TextStyle(fontSize: 14),
          shape: RoundedRectangleBorder(
              borderRadius:
                  BorderRadius.circular(AppColors.buttonRadius)),
          behavior: SnackBarBehavior.floating,
        ),
      );
}


