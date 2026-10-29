// Compress capture to ~800px JPEG (native codec; keep off heavy Dart UI work).
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_image_compress/flutter_image_compress.dart';

const int kScanLongEdgePx = 800;
const int kScanJpegQuality = 85;

/// Compresses [path] so dimensions are scaled down toward [kScanLongEdgePx].
///
/// Uses the platform channel (must run on the main isolate, not `compute`).
Future<Uint8List> compressScanImage(String path) async {
  final file = File(path);
  if (!await file.exists()) {
    throw StateError('Capture file missing: $path');
  }

  final result = await FlutterImageCompress.compressWithFile(
    path,
    minWidth: kScanLongEdgePx,
    minHeight: kScanLongEdgePx,
    quality: kScanJpegQuality,
    format: CompressFormat.jpeg,
  );

  if (result == null || result.isEmpty) {
    return file.readAsBytes();
  }
  return Uint8List.fromList(result);
}
