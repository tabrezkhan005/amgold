// Product model matching ProductOut / compact product payloads.
class Product {
  const Product({
    required this.id,
    required this.code,
    required this.name,
    required this.category,
    required this.material,
    required this.price,
    this.weightG,
    this.description = '',
    this.differenceNote = '',
    this.unit = 'pcs',
    this.inStock = true,
    this.isActive = true,
    this.primaryPhotoId,
    this.primaryPhotoUrl,
    this.hsnCode,
    this.gstRate,
  });

  final String id;
  final String code;
  final String name;
  final String category;
  final String material;
  final double price;
  final double? weightG;
  final String description;
  final String differenceNote;
  final String unit;
  final bool inStock;
  final bool isActive;
  final String? primaryPhotoId;
  /// Absolute or relative photo URL when the API includes one.
  final String? primaryPhotoUrl;
  final String? hsnCode;
  final double? gstRate;

  /// Human-readable material (never "gold" alone for rolled_gold).
  String get materialLabel {
    if (material == 'rolled_gold') return 'Rolled gold';
    return material.replaceAll('_', ' ');
  }

  /// Prefer explicit photo URL fields when present.
  String? get imageUrl {
    final url = primaryPhotoUrl;
    if (url != null && url.isNotEmpty) return url;
    return null;
  }

  static double _num(dynamic v, [double fallback = 0]) {
    if (v == null) return fallback;
    if (v is num) return v.toDouble();
    if (v is String) return double.tryParse(v) ?? fallback;
    return fallback;
  }

  static double? _numOrNull(dynamic v) {
    if (v == null) return null;
    if (v is num) return v.toDouble();
    if (v is String) return double.tryParse(v);
    return null;
  }

  factory Product.fromJson(Map<String, dynamic> json) {
    final photoUrl = json['primary_photo_url'] as String? ??
        json['thumb_url'] as String? ??
        json['photo_url'] as String? ??
        json['image'] as String?;

    return Product(
      id: json['id'].toString(),
      code: json['code'] as String? ?? json['id']?.toString() ?? '',
      name: json['name'] as String? ?? '',
      category: json['category'] as String? ?? 'other',
      material: json['material'] as String? ?? 'rolled_gold',
      price: _num(json['price']),
      weightG: _numOrNull(json['weight_g']),
      description: json['description'] as String? ?? '',
      differenceNote: json['difference_note'] as String? ??
          json['difference'] as String? ??
          '',
      unit: json['unit'] as String? ?? 'pcs',
      inStock: json['in_stock'] as bool? ?? true,
      isActive: json['is_active'] as bool? ?? json['active'] as bool? ?? true,
      primaryPhotoId: json['primary_photo_id']?.toString(),
      primaryPhotoUrl: (photoUrl != null && photoUrl.isNotEmpty) ? photoUrl : null,
      hsnCode: json['hsn_code'] as String?,
      gstRate: _numOrNull(json['gst_rate']),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'code': code,
        'name': name,
        'category': category,
        'material': material,
        'price': price,
        'weight_g': weightG,
        'description': description,
        'difference_note': differenceNote,
        'unit': unit,
        'in_stock': inStock,
        'is_active': isActive,
        'primary_photo_id': primaryPhotoId,
        if (primaryPhotoUrl != null) 'primary_photo_url': primaryPhotoUrl,
        'hsn_code': hsnCode,
        'gst_rate': gstRate,
      };

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Product &&
          runtimeType == other.runtimeType &&
          id == other.id &&
          code == other.code &&
          price == other.price;

  @override
  int get hashCode => Object.hash(id, code, price);
}
