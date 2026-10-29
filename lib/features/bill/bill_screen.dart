// Bill cart: Send to billing desk (cloud draft relay).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/currency.dart';
import '../../widgets/primary_button.dart';
import 'bill_controller.dart';

class BillScreen extends ConsumerStatefulWidget {
  const BillScreen({super.key});

  @override
  ConsumerState<BillScreen> createState() => _BillScreenState();
}

class _BillScreenState extends ConsumerState<BillScreen> {
  late final TextEditingController _nameCtrl;
  late final TextEditingController _phoneCtrl;
  late final TextEditingController _discountCtrl;
  late final TextEditingController _notesCtrl;
  bool _busy = false;
  String? _lastStatus;

  @override
  void initState() {
    super.initState();
    final draft = ref.read(billControllerProvider);
    _nameCtrl = TextEditingController(text: draft.customerName);
    _phoneCtrl = TextEditingController(text: draft.customerPhone);
    _discountCtrl = TextEditingController(
      text: draft.discount == 0 ? '' : draft.discount.toStringAsFixed(0),
    );
    _notesCtrl = TextEditingController(text: draft.notes);
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _phoneCtrl.dispose();
    _discountCtrl.dispose();
    _notesCtrl.dispose();
    super.dispose();
  }

  void _syncCustomer() {
    ref.read(billControllerProvider.notifier).setCustomer(
          name: _nameCtrl.text.trim(),
          phone: _phoneCtrl.text.trim(),
          notes: _notesCtrl.text.trim(),
        );
    final raw = _discountCtrl.text.trim();
    final value = double.tryParse(raw) ?? 0;
    ref.read(billControllerProvider.notifier).setDiscount(value);
  }

  Future<void> _sendToDesk() async {
    final draft = ref.read(billControllerProvider);
    if (draft.items.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Add items before sending')),
      );
      return;
    }

    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Send to billing desk?',
                style: Theme.of(ctx).textTheme.titleLarge,
              ),
              const SizedBox(height: 8),
              Text(
                '${draft.itemCount} item(s) · indicative ${formatInr(draft.total)}. '
                'Final tax and total are calculated at the billing desk.',
              ),
              const SizedBox(height: 20),
              PrimaryButton(
                label: 'Confirm send',
                onPressed: () => Navigator.pop(ctx, true),
              ),
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('Cancel'),
              ),
            ],
          ),
        );
      },
    );
    if (confirmed != true) return;

    _syncCustomer();
    setState(() {
      _busy = true;
      _lastStatus = null;
    });

    try {
      final current = ref.read(billControllerProvider);
      final clientDraftId = const Uuid().v4();
      final items = current.items
          .map(
            (i) => {
              'product_id': i.product.id,
              'code': i.product.code,
              'name': i.product.name,
              'unit_price': i.unitPrice,
              'quantity': i.quantity,
              'unit': i.product.unit,
            },
          )
          .toList();

      final remote = await ref.read(apiClientProvider).createBillDraft(
            clientDraftId: clientDraftId,
            customerName: current.customerName.isEmpty
                ? null
                : current.customerName,
            customerPhone: current.customerPhone.isEmpty
                ? null
                : current.customerPhone,
            notes: current.notes.isEmpty ? null : current.notes,
            discountAmount:
                current.discount > 0 ? current.discount : null,
            items: items,
          );

      ref.read(billControllerProvider.notifier).clear();
      _nameCtrl.clear();
      _phoneCtrl.clear();
      _discountCtrl.clear();
      _notesCtrl.clear();

      if (!mounted) return;
      setState(() => _lastStatus = remote.statusLabel);
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Sent to desk'),
          content: Text(
            'Status: ${remote.statusLabel}. '
            'Open Mobile Bills in InvGen to import and print.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('OK'),
            ),
            FilledButton(
              onPressed: () {
                Navigator.pop(ctx);
                context.push('/history');
              },
              child: const Text('View history'),
            ),
          ],
        ),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message)),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Send failed: $e')),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _clear() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Clear bill?'),
        content: const Text('This removes all line items from the current bill.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Clear'),
          ),
        ],
      ),
    );
    if (ok == true) {
      ref.read(billControllerProvider.notifier).clear();
      _nameCtrl.clear();
      _phoneCtrl.clear();
      _discountCtrl.clear();
      _notesCtrl.clear();
      setState(() => _lastStatus = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final draft = ref.watch(billControllerProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Bill'),
        actions: [
          IconButton(
            tooltip: 'History',
            onPressed: () => context.push('/history'),
            icon: const Icon(Icons.history),
          ),
        ],
      ),
      body: Column(
        children: [
          if (_lastStatus != null)
            Material(
              color: AppColors.gold.withValues(alpha: 0.2),
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Text(
                  'Last send: $_lastStatus',
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          Expanded(
            child: draft.items.isEmpty
                ? const Center(
                    child: Text('No items yet. Scan or search to add.'),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
                    itemCount: draft.items.length,
                    itemBuilder: (context, i) {
                      final item = draft.items[i];
                      return Dismissible(
                        key: ValueKey(item.product.id),
                        direction: DismissDirection.endToStart,
                        background: Container(
                          alignment: Alignment.centerRight,
                          padding: const EdgeInsets.only(right: 20),
                          color: Colors.red.shade400,
                          child: const Icon(Icons.delete, color: Colors.white),
                        ),
                        onDismissed: (_) => ref
                            .read(billControllerProvider.notifier)
                            .removeProduct(item.product.id),
                        child: Card(
                          child: ListTile(
                            title: Text(item.product.name),
                            subtitle: Text(
                              '${item.product.code} · ${item.product.materialLabel} · ${formatInr(item.unitPrice)}',
                            ),
                            trailing: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                IconButton(
                                  onPressed: () => ref
                                      .read(billControllerProvider.notifier)
                                      .updateQuantity(
                                        item.product.id,
                                        item.quantity - 1,
                                      ),
                                  icon: const Icon(Icons.remove_circle_outline),
                                ),
                                Text('${item.quantity}'),
                                IconButton(
                                  onPressed: () => ref
                                      .read(billControllerProvider.notifier)
                                      .updateQuantity(
                                        item.product.id,
                                        item.quantity + 1,
                                      ),
                                  icon: const Icon(Icons.add_circle_outline),
                                ),
                                const SizedBox(width: 4),
                                Text(
                                  formatInr(item.lineTotal),
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                    color: AppColors.goldMuted,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),
          Material(
            elevation: 8,
            color: Theme.of(context).colorScheme.surface,
            child: SafeArea(
              top: false,
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextField(
                      controller: _nameCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Customer name',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      onChanged: (_) => _syncCustomer(),
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _phoneCtrl,
                      keyboardType: TextInputType.phone,
                      decoration: const InputDecoration(
                        labelText: 'Customer phone',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      onChanged: (_) => _syncCustomer(),
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _discountCtrl,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Flat discount (INR)',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      onChanged: (_) => _syncCustomer(),
                    ),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _notesCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Notes',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      onChanged: (_) => _syncCustomer(),
                    ),
                    const SizedBox(height: 12),
                    _Totals(
                      subtotal: draft.subtotal,
                      discount: draft.discount,
                      total: draft.total,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Indicative only — final tax and total at the billing desk.',
                      style: Theme.of(context).textTheme.bodySmall,
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 12),
                    PrimaryButton(
                      label: 'Send to billing desk',
                      loading: _busy,
                      onPressed: _busy ? null : _sendToDesk,
                    ),
                    TextButton(
                      onPressed: draft.items.isEmpty ? null : _clear,
                      child: const Text('Clear bill'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Totals extends StatelessWidget {
  const _Totals({
    required this.subtotal,
    required this.discount,
    required this.total,
  });

  final double subtotal;
  final double discount;
  final double total;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _row('Subtotal', formatInr(subtotal)),
        if (discount > 0) _row('Discount', '- ${formatInr(discount)}'),
        const Divider(),
        _row('Indicative total', formatInr(total), bold: true),
      ],
    );
  }

  Widget _row(String label, String value, {bool bold = false}) {
    final style = bold
        ? const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)
        : const TextStyle();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: style),
          Text(value, style: style.copyWith(color: AppColors.goldMuted)),
        ],
      ),
    );
  }
}
