// Side-by-side look-alike compare sheet. Never auto-selects.
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/utils/currency.dart';
import '../../../models/match_result.dart';

Future<void> showCompareSheet(
  BuildContext context, {
  required List<MatchResult> matches,
  required Future<void> Function(String productId) onChoose,
}) {
  final top = matches.take(3).toList();
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => _CompareSheetBody(matches: top, onChoose: onChoose),
  );
}

class _CompareSheetBody extends ConsumerWidget {
  const _CompareSheetBody({
    required this.matches,
    required this.onChoose,
  });

  final List<MatchResult> matches;
  final Future<void> Function(String productId) onChoose;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.watch(apiClientProvider);

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.black26,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Confirm the exact design',
            style: Theme.of(context).textTheme.titleLarge,
          ),
          const SizedBox(height: 4),
          Text(
            'These look alike. Tap one to open details. Nothing is auto-selected.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 280,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: matches.length,
              separatorBuilder: (_, _) => const SizedBox(width: 12),
              itemBuilder: (context, i) {
                final m = matches[i];
                final url = api.resolvePhotoUrl(m.product.imageUrl);
                return InkWell(
                  onTap: () async {
                    Navigator.pop(context);
                    await onChoose(m.product.id);
                  },
                  borderRadius: BorderRadius.circular(16),
                  child: Container(
                    width: 160,
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      border: Border.all(color: AppColors.gold),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(12),
                          child: url == null
                              ? Container(
                                  width: 144,
                                  height: 120,
                                  color: Colors.black12,
                                  alignment: Alignment.center,
                                  child: const Icon(Icons.diamond_outlined),
                                )
                              : CachedNetworkImage(
                                  imageUrl: url,
                                  width: 144,
                                  height: 120,
                                  fit: BoxFit.cover,
                                  errorWidget: (_, _, _) =>
                                      const SizedBox(height: 120),
                                ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          m.code,
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                        Text(
                          m.product.name,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        if (m.product.differenceNote.isNotEmpty)
                          Text(
                            m.product.differenceNote,
                            style: Theme.of(context)
                                .textTheme
                                .bodySmall
                                ?.copyWith(color: AppColors.goldMuted),
                          ),
                        Text(formatInr(m.product.price)),
                      ],
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
