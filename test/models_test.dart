import 'package:flutter_test/flutter_test.dart';

import 'package:amgold/models/match_result.dart';
import 'package:amgold/models/product.dart';
import 'package:amgold/models/scan_result.dart';

void main() {
  test('Product.fromJson maps ProductOut fields and rolled_gold label', () {
    final p = Product.fromJson({
      'id': '11111111-1111-1111-1111-111111111111',
      'code': 'AMG-0001',
      'name': 'Bead Necklace (10 beads)',
      'category': 'necklace',
      'material': 'rolled_gold',
      'price': '450.00',
      'weight_g': '22.0',
      'description': 'x',
      'difference_note': '10 beads',
      'unit': 'pcs',
      'in_stock': true,
      'is_active': true,
      'primary_photo_id': null,
    });
    expect(p.materialLabel, 'Rolled gold');
    expect(p.code, 'AMG-0001');
    expect(p.differenceNote, '10 beads');
    expect(p.price, 450.0);
    expect(p.toJson()['weight_g'], 22.0);
  });

  test('ScanResult.fromJson parses matches and flags', () {
    final json = {
      'scan_id': 'abc',
      'matches': [
        {
          'product_id': 'P001',
          'code': 'AMG-0001',
          'score': 0.87,
          'rank': 1,
          'source': 'visual',
          'product': {
            'id': 'P001',
            'code': 'AMG-0001',
            'name': 'A',
            'category': 'necklace',
            'material': 'rolled_gold',
            'price': 1,
            'weight_g': 1,
            'description': '',
            'difference_note': '10 beads',
            'is_active': true,
          },
        },
      ],
      'top_score': 0.87,
      'margin': 0.02,
      'ambiguous': true,
      'low_confidence': false,
      'latency_ms': 120,
    };
    final result = ScanResult.fromJson(json);
    expect(result.ambiguous, isTrue);
    expect(result.matches.first, isA<MatchResult>());
    expect(result.matches.first.product.id, 'P001');
    expect(result.matches.first.code, 'AMG-0001');
  });
}
