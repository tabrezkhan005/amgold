// Holds the latest successful /scan payload for the Results screen.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/scan_result.dart';

class LatestScanNotifier extends Notifier<ScanResult?> {
  @override
  ScanResult? build() => null;

  void setResult(ScanResult result) => state = result;

  void clear() => state = null;
}

final latestScanProvider =
    NotifierProvider<LatestScanNotifier, ScanResult?>(LatestScanNotifier.new);

/// Local path of the last captured JPEG (for Hero / preview).
class LastCapturePathNotifier extends Notifier<String?> {
  @override
  String? build() => null;

  void setPath(String? path) => state = path;
}

final lastCapturePathProvider =
    NotifierProvider<LastCapturePathNotifier, String?>(
  LastCapturePathNotifier.new,
);
