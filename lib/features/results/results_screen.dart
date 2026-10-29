// Match results: clear / ambiguous / low_confidence. Never auto-select.
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_client.dart';
import '../../core/theme/app_colors.dart';
import '../../widgets/bill_badge_button.dart';
import '../../widgets/error_view.dart';
import '../../widgets/primary_button.dart';
import '../scan/scan_result_provider.dart';
import 'widgets/compare_sheet.dart';
import 'widgets/match_card.dart';

class ResultsScreen extends ConsumerWidget {
  const ResultsScreen({super.key});

  Future<void> _chooseProduct(
    WidgetRef ref,
    BuildContext context,
    String productId,
  ) async {
    final result = ref.read(latestScanProvider);
    if (result != null) {
      try {
        await ref.read(apiClientProvider).sendScanFeedback(
              scanId: result.scanId,
              chosenProductId: productId,
            );
      } catch (_) {
        // Feedback is best-effort; still open the product.
      }
    }
    if (context.mounted) context.push('/product/$productId');
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final result = ref.watch(latestScanProvider);

    if (result == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Results')),
        body: ErrorView(
          message: 'No scan result yet. Capture a design first.',
          onRetry: () => context.go('/scan'),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Results'),
        actions: [
          IconButton(
            tooltip: 'Search manually',
            onPressed: () => context.push('/search'),
            icon: const Icon(Icons.search),
          ),
          const BillBadgeButton(color: Colors.black87),
        ],
      ),
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (result.lowConfidence)
            _Banner(
              color: Colors.orange.shade100,
              icon: Icons.search_off,
              text: 'No confident match',
            )
          else if (result.ambiguous)
            _Banner(
              color: AppColors.gold.withValues(alpha: 0.25),
              icon: Icons.compare,
              text: 'Close matches. Confirm the exact design.',
              actionLabel: 'Compare',
              onAction: () => showCompareSheet(
                context,
                matches: result.matches,
                onChoose: (id) => _chooseProduct(ref, context, id),
              ),
            ),
          Expanded(
            child: result.lowConfidence
                ? Padding(
                    padding: const EdgeInsets.all(24),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          'Try another angle or better lighting, or search by name/code.',
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.bodyLarge,
                        ),
                        const SizedBox(height: 24),
                        PrimaryButton(
                          label: 'Retake',
                          onPressed: () => context.go('/scan'),
                        ),
                        const SizedBox(height: 12),
                        OutlinedButton(
                          onPressed: () => context.push('/search'),
                          child: const Text('Search manually'),
                        ),
                      ],
                    ),
                  )
                : ListView(
                    padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                    children: [
                      Text(
                        'Top matches',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        height: 280,
                        child: ListView.separated(
                          scrollDirection: Axis.horizontal,
                          itemCount: result.matches.length,
                          separatorBuilder: (_, _) => const SizedBox(width: 12),
                          itemBuilder: (context, i) {
                            final m = result.matches[i];
                            return MatchCard(
                              match: m,
                              // Emphasize top only when not ambiguous — never auto-select.
                              emphasized: i == 0 && !result.ambiguous,
                              onTap: () =>
                                  _chooseProduct(ref, context, m.product.id),
                            )
                                .animate()
                                .fadeIn(duration: 200.ms, delay: (40 * i).ms)
                                .slideX(
                                  begin: 0.05,
                                  duration: 220.ms,
                                  delay: (40 * i).ms,
                                );
                          },
                        ),
                      ),
                      if (result.ambiguous) ...[
                        const SizedBox(height: 16),
                        PrimaryButton(
                          label: 'Compare look-alikes',
                          onPressed: () => showCompareSheet(
                            context,
                            matches: result.matches,
                            onChoose: (id) =>
                                _chooseProduct(ref, context, id),
                          ),
                        ),
                      ],
                      const SizedBox(height: 12),
                      Text(
                        'Tap a card to open details. Nothing is added until you confirm.',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({
    required this.color,
    required this.icon,
    required this.text,
    this.actionLabel,
    this.onAction,
  });

  final Color color;
  final IconData icon;
  final String text;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 0),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Icon(icon, color: AppColors.charcoal),
          const SizedBox(width: 10),
          Expanded(child: Text(text)),
          if (actionLabel != null && onAction != null)
            TextButton(onPressed: onAction, child: Text(actionLabel!)),
        ],
      ),
    );
  }
}
