// Persistent bill badge with item count.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/theme/app_colors.dart';
import '../features/bill/bill_controller.dart';

class BillBadgeButton extends ConsumerWidget {
  const BillBadgeButton({super.key, this.color = Colors.white});

  final Color color;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final count = ref.watch(billControllerProvider).itemCount;
    return IconButton(
      tooltip: 'Bill',
      onPressed: () => context.push('/bill'),
      icon: Stack(
        clipBehavior: Clip.none,
        children: [
          Icon(Icons.receipt_long, color: color),
          if (count > 0)
            Positioned(
              right: -6,
              top: -4,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                decoration: BoxDecoration(
                  color: AppColors.gold,
                  borderRadius: BorderRadius.circular(10),
                ),
                constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
                child: Text(
                  '$count',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: AppColors.onGold,
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}
