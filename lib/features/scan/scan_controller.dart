// Camera lifecycle and scan request state.
import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart' show Offset;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_exception.dart';
import '../../core/utils/haptics.dart';
import '../../core/utils/image_compress.dart';
import 'scan_result_provider.dart';

enum ScanPhase { idle, capturing, uploading, done, error }

class ScanUiState {
  const ScanUiState({
    this.phase = ScanPhase.idle,
    this.errorMessage,
    this.controller,
    this.cameras = const [],
    this.permissionDenied = false,
    this.initError,
    this.flashOn = false,
    this.previewReady = false,
  });

  final ScanPhase phase;
  final String? errorMessage;
  final CameraController? controller;
  final List<CameraDescription> cameras;
  final bool permissionDenied;
  final String? initError;
  final bool flashOn;
  final bool previewReady;

  bool get isBusy =>
      phase == ScanPhase.capturing || phase == ScanPhase.uploading;

  bool get isCameraReady {
    final c = controller;
    return c != null &&
        previewReady &&
        c.value.isInitialized &&
        c.value.previewSize != null;
  }

  ScanUiState copyWith({
    ScanPhase? phase,
    String? errorMessage,
    CameraController? controller,
    List<CameraDescription>? cameras,
    bool? permissionDenied,
    String? initError,
    bool? flashOn,
    bool? previewReady,
    bool clearError = false,
    bool clearController = false,
  }) {
    return ScanUiState(
      phase: phase ?? this.phase,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      controller: clearController ? null : (controller ?? this.controller),
      cameras: cameras ?? this.cameras,
      permissionDenied: permissionDenied ?? this.permissionDenied,
      initError: initError ?? this.initError,
      flashOn: flashOn ?? this.flashOn,
      previewReady: clearController
          ? false
          : (previewReady ?? this.previewReady),
    );
  }
}

class ScanController extends Notifier<ScanUiState> {
  CameraController? _owned;

  @override
  ScanUiState build() {
    ref.onDispose(() {
      _detachOwned();
    });
    return const ScanUiState();
  }

  void _onCameraTick() {
    final c = _owned;
    if (c == null) return;
    final ready =
        c.value.isInitialized && c.value.previewSize != null;
    if (ready != state.previewReady || c != state.controller) {
      state = state.copyWith(controller: c, previewReady: ready);
    }
  }

  void _detachOwned() {
    final c = _owned;
    _owned = null;
    if (c != null) {
      c.removeListener(_onCameraTick);
      c.dispose();
    }
  }

  Future<void> initCamera() async {
    await disposeCamera();
    state = state.copyWith(
      permissionDenied: false,
      initError: null,
      clearError: true,
      flashOn: false,
      previewReady: false,
    );
    CameraController? controller;
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        state = state.copyWith(initError: 'No camera found on this device.');
        return;
      }
      final back = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      controller = CameraController(
        back,
        ResolutionPreset.high,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );
      controller.addListener(_onCameraTick);
      await controller.initialize();
      // Some OEMs leave previewSize null for a few frames after initialize.
      for (var i = 0; i < 40 && controller.value.previewSize == null; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 50));
      }
      if (controller.value.previewSize == null) {
        controller.removeListener(_onCameraTick);
        await controller.dispose();
        controller = null;
        state = state.copyWith(
          initError: 'Camera started but preview is not ready. Tap Retry.',
          clearController: true,
        );
        return;
      }
      _owned = controller;
      state = state.copyWith(
        controller: controller,
        cameras: cameras,
        previewReady: true,
      );
    } on CameraException catch (e) {
      if (controller != null) {
        controller.removeListener(_onCameraTick);
        await controller.dispose();
      }
      final denied = e.code == 'CameraAccessDenied' ||
          e.code == 'CameraAccessDeniedWithoutPrompt' ||
          e.code == 'AudioAccessDenied';
      state = state.copyWith(
        permissionDenied: denied,
        initError: denied ? null : (e.description ?? e.code),
        clearController: true,
      );
    } catch (e) {
      if (controller != null) {
        controller.removeListener(_onCameraTick);
        await controller.dispose();
      }
      state = state.copyWith(
        initError: e.toString(),
        clearController: true,
      );
    }
  }

  Future<void> disposeCamera() async {
    _detachOwned();
    state = state.copyWith(clearController: true, previewReady: false);
  }

  Future<void> toggleFlash() async {
    final c = state.controller;
    if (c == null || !c.value.isInitialized) return;
    final next = !state.flashOn;
    try {
      await c.setFlashMode(next ? FlashMode.torch : FlashMode.off);
      state = state.copyWith(flashOn: next);
    } on CameraException catch (e) {
      state = state.copyWith(errorMessage: e.description ?? 'Flash unavailable');
    }
  }

  Future<void> focusAt(Offset normalized) async {
    final c = state.controller;
    if (c == null || !c.value.isInitialized) return;
    try {
      await c.setFocusPoint(normalized);
      await c.setExposurePoint(normalized);
    } on CameraException {
      // Some devices reject focus points; ignore quietly.
    }
  }

  /// Returns true when a ScanResult was stored and navigation should follow.
  Future<bool> captureAndScan() async {
    final controller = state.controller;
    if (!state.isCameraReady || state.isBusy || controller == null) {
      return false;
    }

    state = state.copyWith(phase: ScanPhase.capturing, clearError: true);
    await hapticCapture();

    try {
      final shot = await controller.takePicture();
      ref.read(lastCapturePathProvider.notifier).setPath(shot.path);
      state = state.copyWith(phase: ScanPhase.uploading);

      final bytes = await compressScanImage(shot.path);
      final api = ref.read(apiClientProvider);
      final result = await api.scanImage(bytes);
      ref.read(latestScanProvider.notifier).setResult(result);

      state = state.copyWith(phase: ScanPhase.done);
      return true;
    } on ApiException catch (e) {
      state = state.copyWith(
        phase: ScanPhase.error,
        errorMessage: e.message,
      );
      return false;
    } catch (e, st) {
      debugPrint('scan failed: $e\n$st');
      state = state.copyWith(
        phase: ScanPhase.error,
        errorMessage: e.toString(),
      );
      return false;
    }
  }

  void clearError() {
    state = state.copyWith(phase: ScanPhase.idle, clearError: true);
  }
}

final scanControllerProvider =
    NotifierProvider<ScanController, ScanUiState>(ScanController.new);
