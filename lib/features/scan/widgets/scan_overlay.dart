// Focus frame and scanning-line overlay.
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../../core/theme/app_colors.dart';

class ScanOverlay extends StatelessWidget {
  const ScanOverlay({
    super.key,
    required this.scanning,
  });

  final bool scanning;

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: LayoutBuilder(
        builder: (context, constraints) {
          final side = constraints.biggest.shortestSide * 0.72;
          return Stack(
            alignment: Alignment.center,
            children: [
              Container(
                width: side,
                height: side,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: AppColors.gold, width: 2),
                ),
              ),
              if (scanning)
                SizedBox(
                  width: side,
                  height: side,
                  child: Align(
                    alignment: Alignment.topCenter,
                    child: Container(
                      height: 2,
                      margin: const EdgeInsets.symmetric(horizontal: 8),
                      color: AppColors.gold.withValues(alpha: 0.9),
                    )
                        .animate(onPlay: (c) => c.repeat(reverse: true))
                        .moveY(
                          begin: 8,
                          end: side - 10,
                          duration: 1400.ms,
                          curve: Curves.easeInOut,
                        ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
