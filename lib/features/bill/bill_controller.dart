// Cart / bill draft mutations (phone side; tax owned by desk).
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/bill_item.dart';
import '../../models/product.dart';

class BillDraft {
  const BillDraft({
    this.items = const [],
    this.discount = 0,
    this.customerName = '',
    this.customerPhone = '',
    this.notes = '',
  });

  final List<BillItem> items;
  final double discount;
  final String customerName;
  final String customerPhone;
  final String notes;

  int get itemCount => items.fold(0, (s, i) => s + i.quantity);

  double get subtotal => items.fold(0, (s, i) => s + i.lineTotal);

  /// Indicative total only — desk computes final tax and totals.
  double get total => (subtotal - discount).clamp(0, double.infinity);

  BillDraft copyWith({
    List<BillItem>? items,
    double? discount,
    String? customerName,
    String? customerPhone,
    String? notes,
  }) {
    return BillDraft(
      items: items ?? this.items,
      discount: discount ?? this.discount,
      customerName: customerName ?? this.customerName,
      customerPhone: customerPhone ?? this.customerPhone,
      notes: notes ?? this.notes,
    );
  }
}

class BillController extends Notifier<BillDraft> {
  @override
  BillDraft build() => const BillDraft();

  void addProduct(Product product, {int quantity = 1}) {
    final qty = quantity.clamp(1, 999);
    final items = [...state.items];
    final idx = items.indexWhere((i) => i.product.id == product.id);
    if (idx >= 0) {
      final existing = items[idx];
      items[idx] = existing.copyWith(
        quantity: (existing.quantity + qty).clamp(1, 999),
      );
    } else {
      items.add(
        BillItem(
          product: product,
          quantity: qty,
          unitPrice: product.price,
        ),
      );
    }
    state = state.copyWith(items: items);
  }

  void updateQuantity(String productId, int quantity) {
    if (quantity <= 0) {
      removeProduct(productId);
      return;
    }
    final q = quantity.clamp(1, 999);
    final items = [
      for (final i in state.items)
        if (i.product.id == productId) i.copyWith(quantity: q) else i,
    ];
    state = state.copyWith(items: items);
  }

  void removeProduct(String productId) {
    state = state.copyWith(
      items: state.items.where((i) => i.product.id != productId).toList(),
    );
  }

  void setDiscount(double value) {
    state = state.copyWith(discount: value < 0 ? 0 : value);
  }

  void setCustomer({String? name, String? phone, String? notes}) {
    state = state.copyWith(
      customerName: name ?? state.customerName,
      customerPhone: phone ?? state.customerPhone,
      notes: notes ?? state.notes,
    );
  }

  void clear() => state = const BillDraft();
}

final billControllerProvider =
    NotifierProvider<BillController, BillDraft>(BillController.new);
