import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:amgold/features/results/results_screen.dart';
import 'package:amgold/features/scan/scan_result_provider.dart';
import 'package:amgold/models/match_result.dart';
import 'package:amgold/models/product.dart';
import 'package:amgold/models/scan_result.dart';

Product _p(String id, String name, String differenceNote) {
  return Product(
    id: id,
    code: 'AMG-$id',
    name: name,
    category: 'necklace',
    material: 'rolled_gold',
    price: 450,
    weightG: 20,
    description: 'PLACEHOLDER',
    differenceNote: differenceNote,
  );
}

ScanResult _ambiguousResult() {
  final p1 = _p('P001', 'Bead Necklace (10 beads)', '10 beads');
  final p2 = _p('P002', 'Bead Necklace (8 beads)', '8 beads');
  return ScanResult(
    scanId: 'test-scan',
    matches: [
      MatchResult(
        productId: 'P001',
        code: p1.code,
        score: 0.88,
        rank: 1,
        source: 'visual',
        product: p1,
      ),
      MatchResult(
        productId: 'P002',
        code: p2.code,
        score: 0.85,
        rank: 2,
        source: 'catalog_similar',
        product: p2,
      ),
    ],
    topScore: 0.88,
    margin: 0.03,
    ambiguous: true,
    lowConfidence: false,
    latencyMs: 100,
  );
}

class _SeededScan extends LatestScanNotifier {
  @override
  ScanResult? build() => _ambiguousResult();
}

class _LowConfidenceScan extends LatestScanNotifier {
  @override
  ScanResult? build() => const ScanResult(
        scanId: 'low',
        matches: [],
        topScore: 0.2,
        margin: 0,
        ambiguous: false,
        lowConfidence: true,
        latencyMs: 50,
      );
}

void main() {
  testWidgets('ambiguous results show banner and never auto-select copy',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          latestScanProvider.overrideWith(_SeededScan.new),
        ],
        child: const MaterialApp(home: ResultsScreen()),
      ),
    );
    // Avoid pumpAndSettle — flutter_animate shimmer loops forever.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(
      find.textContaining('Close matches'),
      findsOneWidget,
    );
    expect(find.text('Compare look-alikes'), findsOneWidget);
    expect(
      find.textContaining('Nothing is added until you confirm'),
      findsOneWidget,
    );
    expect(find.text('Compare'), findsWidgets);
  });

  testWidgets('low confidence shows retake path', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          latestScanProvider.overrideWith(_LowConfidenceScan.new),
        ],
        child: const MaterialApp(home: ResultsScreen()),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('No confident match'), findsOneWidget);
    expect(find.text('Retake'), findsOneWidget);
    expect(find.text('Search manually'), findsOneWidget);
  });
}
