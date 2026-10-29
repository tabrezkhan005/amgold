// Debounced manual search over GET /v1/products.
import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/currency.dart';
import '../../models/product.dart';
import '../../widgets/error_view.dart';

class ManualSearchScreen extends ConsumerStatefulWidget {
  const ManualSearchScreen({super.key});

  @override
  ConsumerState<ManualSearchScreen> createState() => _ManualSearchScreenState();
}

class _ManualSearchScreenState extends ConsumerState<ManualSearchScreen> {
  final _ctrl = TextEditingController();
  Timer? _debounce;
  List<Product> _items = const [];
  bool _loading = false;
  String? _error;
  String _lastQuery = '';

  @override
  void initState() {
    super.initState();
    _search('');
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _ctrl.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      _search(value.trim());
    });
  }

  Future<void> _search(String q) async {
    setState(() {
      _loading = true;
      _error = null;
      _lastQuery = q;
    });
    try {
      final result = await ref.read(apiClientProvider).listProducts(q: q);
      if (!mounted || _lastQuery != q) return;
      setState(() {
        _items = result.items.where((p) => p.isActive).toList();
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = ref.watch(apiClientProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Manual search')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _ctrl,
              onChanged: _onChanged,
              decoration: const InputDecoration(
                hintText: 'Search by code or name',
                prefixIcon: Icon(Icons.search),
                border: OutlineInputBorder(),
              ),
            ),
          ),
          if (_loading) const LinearProgressIndicator(),
          Expanded(
            child: _error != null
                ? ErrorView(
                    message: _error!,
                    onRetry: () => _search(_ctrl.text.trim()),
                  )
                : _items.isEmpty
                    ? const Center(child: Text('No products found'))
                    : ListView.separated(
                        itemCount: _items.length,
                        separatorBuilder: (_, _) => const Divider(height: 1),
                        itemBuilder: (context, i) {
                          final p = _items[i];
                          final url = api.resolvePhotoUrl(p.imageUrl);
                          return ListTile(
                            leading: ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: url == null
                                  ? Container(
                                      width: 56,
                                      height: 56,
                                      color: Colors.black12,
                                      alignment: Alignment.center,
                                      child: const Icon(Icons.diamond_outlined),
                                    )
                                  : CachedNetworkImage(
                                      imageUrl: url,
                                      width: 56,
                                      height: 56,
                                      fit: BoxFit.cover,
                                      errorWidget: (_, _, _) =>
                                          const SizedBox(width: 56, height: 56),
                                    ),
                            ),
                            title: Text(p.name),
                            subtitle: Text(
                              '${p.code} · ${p.materialLabel}',
                              style: TextStyle(color: AppColors.goldMuted),
                            ),
                            trailing: Text(formatInr(p.price)),
                            onTap: () => context.push('/product/${p.id}'),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
