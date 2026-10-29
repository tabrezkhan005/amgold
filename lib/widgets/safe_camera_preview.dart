// Camera preview that never calls aspectRatio while previewSize is null.
import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Drop-in replacement for [CameraPreview] that avoids the package's
/// `previewSize!` null-check crash on some Android devices / lifecycle races.
class SafeCameraPreview extends StatelessWidget {
  const SafeCameraPreview(this.controller, {super.key, this.child});

  final CameraController controller;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<CameraValue>(
      valueListenable: controller,
      builder: (context, value, _) {
        final size = value.previewSize;
        if (!value.isInitialized || size == null || size.width <= 0 || size.height <= 0) {
          return const ColoredBox(
            color: Colors.black,
            child: Center(
              child: CircularProgressIndicator(color: Colors.white54),
            ),
          );
        }

        final ratio = size.width / size.height;
        final landscape = _isLandscape(value);
        return AspectRatio(
          aspectRatio: landscape ? ratio : (1 / ratio),
          child: Stack(
            fit: StackFit.expand,
            children: [
              _wrapInRotatedBox(
                value: value,
                child: controller.buildPreview(),
              ),
              ?child,
            ],
          ),
        );
      },
    );
  }

  bool _isLandscape(CameraValue value) {
    return <DeviceOrientation>[
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ].contains(_applicableOrientation(value));
  }

  Widget _wrapInRotatedBox({
    required CameraValue value,
    required Widget child,
  }) {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) {
      return child;
    }
    return RotatedBox(quarterTurns: _quarterTurns(value), child: child);
  }

  int _quarterTurns(CameraValue value) {
    const turns = <DeviceOrientation, int>{
      DeviceOrientation.portraitUp: 0,
      DeviceOrientation.landscapeRight: 1,
      DeviceOrientation.portraitDown: 2,
      DeviceOrientation.landscapeLeft: 3,
    };
    return turns[_applicableOrientation(value)] ?? 0;
  }

  DeviceOrientation _applicableOrientation(CameraValue value) {
    if (value.isRecordingVideo) {
      return value.recordingOrientation ?? value.deviceOrientation;
    }
    return value.previewPauseOrientation ??
        value.lockedCaptureOrientation ??
        value.deviceOrientation;
  }
}
