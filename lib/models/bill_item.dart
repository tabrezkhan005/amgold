// Bill line item with quantity and unit_price snapshot.
import 'product.dart';

class BillItem {
  const BillItem({
    required this.product,
    required this.quantity,
    required this.unitPrice,
  });

  final Product product;
  final int quantity;
  final double unitPrice;

  double get lineTotal => unitPrice * quantity;

  BillItem copyWith({Product? product, int? quantity, double? unitPrice}) {
    return BillItem(
      product: product ?? this.product,
      quantity: quantity ?? this.quantity,
      unitPrice: unitPrice ?? this.unitPrice,
    );
  }

  factory BillItem.fromJson(Map<String, dynamic> json) {
    return BillItem(
      product: Product.fromJson(json['product'] as Map<String, dynamic>),
      quantity: json['quantity'] as int,
      unitPrice: (json['unit_price'] as num).toDouble(),
    );
  }

  Map<String, dynamic> toJson() => {
        'product': product.toJson(),
        'quantity': quantity,
        'unit_price': unitPrice,
      };

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is BillItem &&
          product.id == other.product.id &&
          quantity == other.quantity &&
          unitPrice == other.unitPrice;

  @override
  int get hashCode => Object.hash(product.id, quantity, unitPrice);
}
