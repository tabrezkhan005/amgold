// Match card with thumbnail, code, name, price, score.
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/network/api_client.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/utils/currency.dart';
import '../../../models/match_result.dart';
import '../../../widgets/skeletons.dart';

class MatchCard extends ConsumerWidget {
  const MatchCard({
    super.key,
    required this.match,
    required this.emphasized,
    required this.onTap,
  });

  final MatchResult match;
  final bool emphasized;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.watch(apiClientProvider);
    final url = api.resolvePhotoUrl(match.product.imageUrl);
    final pct = (match.score * 100).clamp(0, 100).toStringAsFixed(0);

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        width: 168,
        height: 268,
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: emphasized ? AppColors.gold : Colors.black12,
            width: emphasized ? 2 : 1,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Hero(
              tag: 'product-image-${match.product.id}',
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: url == null
                    ? Container(
                        width: 152,
                        height: 120,
                        color: Colors.black12,
                        alignment: Alignment.center,
                        child: const Icon(Icons.diamond_outlined),
                      )
                    : CachedNetworkImage(
                        imageUrl: url,
                        width: 152,
                        height: 120,
                        memCacheWidth: 304,
                        fit: BoxFit.cover,
                        placeholder: (_, _) =>
                            const SkeletonBox(width: 152, height: 120, radius: 12),
                        errorWidget: (_, _, _) => Container(
                          width: 152,
                          height: 120,
                          color: Colors.black12,
                          alignment: Alignment.center,
                          child: const Icon(Icons.image_not_supported_outlined),
                        ),
                      ),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              match.code,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: AppColors.goldMuted,
                  ),
            ),
            Expanded(
              child: Text(
                match.product.name,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.titleSmall,
              ),
            ),
            Text(
              formatInr(match.product.price),
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: AppColors.goldMuted,
                    fontWeight: FontWeight.w600,
                  ),
            ),
            Text(
              '$pct% · ${match.source == 'catalog_similar' ? 'similar' : 'match'}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}
