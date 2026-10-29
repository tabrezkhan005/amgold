// Bill with invoice_no, customer, items, discount, totals.
import 'bill_item.dart';

class Bill {
  const Bill({
    required this.invoiceNo,
    required this.createdAt,
    required this.customerName,
    required this.customerPhone,
    required this.items,
    this.discount = 0,
  });

  final String invoiceNo;
  final DateTime createdAt;
  final String customerName;
  final String customerPhone;
  final List<BillItem> items;
  final double discount;

  double get subtotal =>
      items.fold(0, (sum, item) => sum + item.lineTotal);

  double get total => (subtotal - discount).clamp(0, double.infinity);

  Bill copyWith({
    String? invoiceNo,
    DateTime? createdAt,
    String? customerName,
    String? customerPhone,
    List<BillItem>? items,
    double? discount,
  }) {
    return Bill(
      invoiceNo: invoiceNo ?? this.invoiceNo,
      createdAt: createdAt ?? this.createdAt,
      customerName: customerName ?? this.customerName,
      customerPhone: customerPhone ?? this.customerPhone,
      items: items ?? this.items,
      discount: discount ?? this.discount,
    );
  }

  factory Bill.fromJson(Map<String, dynamic> json) {
    return Bill(
      invoiceNo: json['invoice_no'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
      customerName: json['customer_name'] as String? ?? '',
      customerPhone: json['customer_phone'] as String? ?? '',
      items: (json['items'] as List<dynamic>? ?? const [])
          .map((e) => BillItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      discount: (json['discount'] as num?)?.toDouble() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'invoice_no': invoiceNo,
        'created_at': createdAt.toIso8601String(),
        'customer_name': customerName,
        'customer_phone': customerPhone,
        'items': items.map((i) => i.toJson()).toList(),
        'discount': discount,
        'subtotal': subtotal,
        'total': total,
      };

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Bill && invoiceNo == other.invoiceNo;

  @override
  int get hashCode => invoiceNo.hashCode;
}
