// Server bill draft from POST/GET /v1/bills/drafts.
class BillDraftRemote {
  const BillDraftRemote({
    required this.id,
    required this.status,
    required this.items,
    this.customerName,
    this.customerPhone,
    this.notes,
    this.discountAmount,
    this.createdAt,
    this.deliveredAt,
    this.importedAt,
    this.deskInvoiceRef,
    this.failureReason,
  });

  final String id;
  final String status;
  final List<Map<String, dynamic>> items;
  final String? customerName;
  final String? customerPhone;
  final String? notes;
  final double? discountAmount;
  final DateTime? createdAt;
  final DateTime? deliveredAt;
  final DateTime? importedAt;
  final String? deskInvoiceRef;
  final String? failureReason;

  String get statusLabel {
    switch (status) {
      case 'pending':
        return 'Queued';
      case 'delivered':
        return 'Received by desk';
      case 'imported':
        return 'Imported';
      case 'failed':
        return 'Failed';
      case 'cancelled':
        return 'Cancelled';
      default:
        return status;
    }
  }

  int get itemCount => items.fold<int>(0, (sum, item) {
        final q = item['quantity'];
        if (q is num) return sum + q.round();
        if (q is String) return sum + (double.tryParse(q)?.round() ?? 0);
        return sum;
      });

  factory BillDraftRemote.fromJson(Map<String, dynamic> json) {
    DateTime? parseDt(dynamic v) {
      if (v == null) return null;
      if (v is String) return DateTime.tryParse(v);
      return null;
    }

    double? parseNum(dynamic v) {
      if (v == null) return null;
      if (v is num) return v.toDouble();
      if (v is String) return double.tryParse(v);
      return null;
    }

    final rawItems = json['items'];
    final items = <Map<String, dynamic>>[];
    if (rawItems is List) {
      for (final e in rawItems) {
        if (e is Map<String, dynamic>) {
          items.add(e);
        } else if (e is Map) {
          items.add(Map<String, dynamic>.from(e));
        }
      }
    }

    return BillDraftRemote(
      id: json['id'].toString(),
      status: json['status'] as String? ?? 'pending',
      items: items,
      customerName: json['customer_name'] as String?,
      customerPhone: json['customer_phone'] as String?,
      notes: json['notes'] as String?,
      discountAmount: parseNum(json['discount_amount']),
      createdAt: parseDt(json['created_at']),
      deliveredAt: parseDt(json['delivered_at']),
      importedAt: parseDt(json['imported_at']),
      deskInvoiceRef: json['desk_invoice_ref'] as String?,
      failureReason: json['failure_reason'] as String?,
    );
  }
}
