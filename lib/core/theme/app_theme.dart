// Builds ThemeData from AmGold design tokens.
import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'app_typography.dart';

abstract final class AppTheme {
  /// Warm cream light theme (default). Flip [useDark] for charcoal boutique look.
  static ThemeData build({bool useDark = false}) {
    final colorScheme = useDark
        ? const ColorScheme.dark(
            primary: AppColors.gold,
            onPrimary: AppColors.onGold,
            secondary: AppColors.goldMuted,
            surface: AppColors.surface,
            onSurface: AppColors.cream,
            error: AppColors.error,
          )
        : const ColorScheme.light(
            primary: AppColors.gold,
            onPrimary: AppColors.onGold,
            secondary: AppColors.goldMuted,
            surface: AppColors.cream,
            onSurface: AppColors.charcoal,
            error: AppColors.error,
          );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor:
          useDark ? AppColors.charcoal : AppColors.cream,
      textTheme: AppTypography.textTheme(dark: useDark),
      appBarTheme: AppBarTheme(
        backgroundColor: useDark ? AppColors.charcoal : AppColors.cream,
        foregroundColor: useDark ? AppColors.cream : AppColors.charcoal,
        elevation: 0,
        centerTitle: true,
      ),
      cardTheme: CardThemeData(
        color: useDark ? AppColors.surfaceLight : Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 48),
          backgroundColor: AppColors.gold,
          foregroundColor: AppColors.onGold,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
    );
  }
}
