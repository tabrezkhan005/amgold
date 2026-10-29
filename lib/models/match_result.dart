// Single scan match (product_id, code, score, rank, source, product).
import 'product.dart';

class MatchResult {
  const MatchResult({
    required this.productId,
    required this.code,
    required this.score,
    required this.rank,
    required this.source,
    required this.product,
  });

  final String productId;
  final String code;
  final double score;
  final int rank;
  final String source; // visual | catalog_similar
  final Product product;

  factory MatchResult.fromJson(Map<String, dynamic> json) {
    final productJson = json['product'];
    final Product product;
    if (productJson is Map<String, dynamic>) {
      product = Product.fromJson(productJson);
    } else {
      product = Product(
        id: json['product_id'].toString(),
        code: json['code'] as String? ?? '',
        name: json['code'] as String? ?? 'Product',
        category: 'other',
        material: 'rolled_gold',
        price: 0,
      );
    }
    return MatchResult(
      productId: json['product_id'].toString(),
      code: json['code'] as String? ?? product.code,
      score: (json['score'] as num?)?.toDouble() ?? 0,
      rank: json['rank'] as int? ?? 0,
      source: json['source'] as String? ?? 'visual',
      product: product,
    );
  }

  Map<String, dynamic> toJson() => {
        'product_id': productId,
        'code': code,
        'score': score,
        'rank': rank,
        'source': source,
        'product': product.toJson(),
      };

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is MatchResult &&
          productId == other.productId &&
          score == other.score &&
          rank == other.rank &&
          source == other.source;

  @override
  int get hashCode => Object.hash(productId, score, rank, source);
}
