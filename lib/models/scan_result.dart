// Full /scan response including ambiguous/low_confidence flags.
import 'match_result.dart';

class ScanResult {
  const ScanResult({
    required this.scanId,
    required this.matches,
    required this.topScore,
    required this.margin,
    required this.ambiguous,
    required this.lowConfidence,
    required this.latencyMs,
  });

  final String scanId;
  final List<MatchResult> matches;
  final double topScore;
  final double margin;
  final bool ambiguous;
  final bool lowConfidence;
  final int latencyMs;

  factory ScanResult.fromJson(Map<String, dynamic> json) {
    final rawMatches = json['matches'] as List<dynamic>? ?? const [];
    return ScanResult(
      scanId: json['scan_id'] as String,
      matches: rawMatches
          .map((e) => MatchResult.fromJson(e as Map<String, dynamic>))
          .toList(),
      topScore: (json['top_score'] as num?)?.toDouble() ?? 0,
      margin: (json['margin'] as num?)?.toDouble() ?? 0,
      ambiguous: json['ambiguous'] as bool? ?? false,
      lowConfidence: json['low_confidence'] as bool? ?? false,
      latencyMs: json['latency_ms'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'scan_id': scanId,
        'matches': matches.map((m) => m.toJson()).toList(),
        'top_score': topScore,
        'margin': margin,
        'ambiguous': ambiguous,
        'low_confidence': lowConfidence,
        'latency_ms': latencyMs,
      };

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ScanResult &&
          scanId == other.scanId &&
          ambiguous == other.ambiguous &&
          lowConfidence == other.lowConfidence &&
          topScore == other.topScore;

  @override
  int get hashCode => Object.hash(scanId, ambiguous, lowConfidence, topScore);
}
