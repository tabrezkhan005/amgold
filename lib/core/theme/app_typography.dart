// Text styles (Playfair Display + Inter via google_fonts).
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'app_colors.dart';

abstract final class AppTypography {
  static TextTheme textTheme({required bool dark}) {
    final onSurface = dark ? AppColors.cream : AppColors.charcoal;
    final base = ThemeData(
      brightness: dark ? Brightness.dark : Brightness.light,
    ).textTheme.apply(bodyColor: onSurface, displayColor: onSurface);

    TextStyle playfair(TextStyle? s) =>
        GoogleFonts.playfairDisplay(textStyle: s);

    TextStyle inter(TextStyle? s) => GoogleFonts.inter(textStyle: s);

    return TextTheme(
      displayLarge: playfair(base.displayLarge),
      displayMedium: playfair(base.displayMedium),
      displaySmall: playfair(base.displaySmall),
      headlineLarge: playfair(base.headlineLarge),
      headlineMedium: playfair(base.headlineMedium),
      headlineSmall: playfair(base.headlineSmall),
      titleLarge: playfair(base.titleLarge),
      titleMedium: inter(base.titleMedium),
      titleSmall: inter(base.titleSmall),
      bodyLarge: inter(base.bodyLarge),
      bodyMedium: inter(base.bodyMedium),
      bodySmall: inter(base.bodySmall),
      labelLarge: inter(base.labelLarge),
      labelMedium: inter(base.labelMedium),
      labelSmall: inter(base.labelSmall),
    );
  }
}
