// Product detail, difference note, add to bill.
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/currency.dart';
import '../../core/utils/haptics.dart';
import '../../models/product.dart';
import '../../widgets/error_view.dart';
import '../../widgets/primary_button.dart';
import '../../widgets/skeletons.dart';
import '../bill/bill_controller.dart';

final productProvider =
    FutureProvider.family<Product, String>((ref, id) async {
  return ref.watch(apiClientProvider).getProduct(id);
});

class ProductDetailScreen extends ConsumerStatefulWidget {
  const ProductDetailScreen({super.key, required this.productId});

  final String productId;

  @override
  ConsumerState<ProductDetailScreen> createState() =>
      _ProductDetailScreenState();
}

class _ProductDetailScreenState extends ConsumerState<ProductDetailScreen> {
  int _qty = 1;

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(productProvider(widget.productId));

    return async.when(
      loading: () => Scaffold(
        appBar: AppBar(),
        body: const Padding(
          padding: EdgeInsets.all(16),
          child: Column(
            children: [
              SkeletonBox(width: double.infinity, height: 280, radius: 16),
              SizedBox(height: 16),
              SkeletonBox(width: 200, height: 24),
              SizedBox(height: 8),
              SkeletonBox(width: 120, height: 20),
            ],
          ),
        ),
      ),
      error: (e, _) => Scaffold(
        appBar: AppBar(),
        body: ErrorView(
          message: e is ApiException ? e.message : e.toString(),
          onRetry: () => ref.invalidate(productProvider(widget.productId)),
        ),
      ),
      data: (product) => _buildContent(context, product),
    );
  }

  Widget _buildContent(BuildContext context, Product product) {
    final api = ref.watch(apiClientProvider);
    final url = api.resolvePhotoUrl(product.imageUrl);

    return Scaffold(
      appBar: AppBar(title: Text(product.code)),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
        children: [
          Hero(
            tag: 'product-image-${product.id}',
            child: ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: AspectRatio(
                aspectRatio: 1,
                child: url == null
                    ? Container(
                        color: Colors.black12,
                        alignment: Alignment.center,
                        child: const Icon(Icons.diamond_outlined, size: 48),
                      )
                    : CachedNetworkImage(
                        imageUrl: url,
                        fit: BoxFit.cover,
                        memCacheWidth: 800,
                        errorWidget: (_, _, _) => Container(
                          color: Colors.black12,
                          child: const Icon(Icons.image_not_supported_outlined),
                        ),
                      ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(product.name, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 4),
          Text(
            product.code,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  color: AppColors.goldMuted,
                ),
          ),
          const SizedBox(height: 8),
          Text(
            formatInr(product.price),
            style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  color: AppColors.goldMuted,
                ),
          ),
          const SizedBox(height: 12),
          if (product.weightG != null)
            _MetaRow(label: 'Weight', value: '${product.weightG} g'),
          _MetaRow(label: 'Category', value: product.category),
          _MetaRow(label: 'Material', value: product.materialLabel),
          if (product.differenceNote.isNotEmpty)
            _MetaRow(label: 'Note', value: product.differenceNote),
          if (product.description.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(product.description),
          ],
          const SizedBox(height: 20),
          Text('Quantity', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Row(
            children: [
              IconButton.filledTonal(
                onPressed: _qty > 1 ? () => setState(() => _qty--) : null,
                icon: const Icon(Icons.remove),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Text(
                  '$_qty',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ),
              IconButton.filledTonal(
                onPressed: _qty < 999
                    ? () => setState(() => _qty++)
                    : null,
                icon: const Icon(Icons.add),
              ),
            ],
          ),
          const SizedBox(height: 16),
          PrimaryButton(
            label: 'Add to bill',
            onPressed: () async {
              ref.read(billControllerProvider.notifier).addProduct(
                    product,
                    quantity: _qty,
                  );
              await hapticAddToBill();
              if (!context.mounted) return;
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('Added $_qty x ${product.name}'),
                  action: SnackBarAction(
                    label: 'Bill',
                    onPressed: () => context.push('/bill'),
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _MetaRow extends StatelessWidget {
  const _MetaRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          SizedBox(
            width: 96,
            child: Text(
              label,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: Theme.of(context).textTheme.bodyLarge,
            ),
          ),
        ],
      ),
    );
  }
}
