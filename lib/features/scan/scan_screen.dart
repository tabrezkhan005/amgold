// Full-screen camera capture and upload to /v1/scan.
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/connectivity_provider.dart';
import '../../core/theme/app_colors.dart';
import '../../widgets/bill_badge_button.dart';
import 'scan_controller.dart';
import 'widgets/scan_overlay.dart';

class ScanScreen extends ConsumerStatefulWidget {
  const ScanScreen({super.key});

  @override
  ConsumerState<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends ConsumerState<ScanScreen>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(scanControllerProvider.notifier).initCamera();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    final notifier = ref.read(scanControllerProvider.notifier);
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused) {
      notifier.disposeCamera();
    } else if (state == AppLifecycleState.resumed) {
      notifier.initCamera();
    }
  }

  Future<void> _onCapture() async {
    final offline = ref.read(isOfflineProvider);
    if (offline) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Offline — scanning needs internet. Use manual search.'),
        ),
      );
      return;
    }
    final ok =
        await ref.read(scanControllerProvider.notifier).captureAndScan();
    if (ok && mounted) context.push('/results');
  }

  void _onTapPreview(TapDownDetails details, BoxConstraints constraints) {
    final nx = (details.localPosition.dx / constraints.maxWidth).clamp(0.0, 1.0);
    final ny =
        (details.localPosition.dy / constraints.maxHeight).clamp(0.0, 1.0);
    ref.read(scanControllerProvider.notifier).focusAt(Offset(nx, ny));
  }

  @override
  Widget build(BuildContext context) {
    final scan = ref.watch(scanControllerProvider);
    final controller = scan.controller;
    final offline = ref.watch(isOfflineProvider);

    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
              child: Row(
                children: [
                  IconButton(
                    tooltip: 'Search manually',
                    onPressed: () => context.push('/search'),
                    icon: const Icon(Icons.search, color: Colors.white),
                  ),
                  const Expanded(
                    child: Text(
                      'Scan design',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.white, fontSize: 16),
                    ),
                  ),
                  IconButton(
                    tooltip: 'Flash',
                    onPressed: controller == null
                        ? null
                        : () => ref
                            .read(scanControllerProvider.notifier)
                            .toggleFlash(),
                    icon: Icon(
                      scan.flashOn ? Icons.flash_on : Icons.flash_off,
                      color: scan.flashOn ? AppColors.gold : Colors.white,
                    ),
                  ),
                  const BillBadgeButton(),
                  IconButton(
                    tooltip: 'Settings',
                    onPressed: () => context.push('/settings'),
                    icon: const Icon(Icons.settings, color: Colors.white70),
                  ),
                ],
              ),
            ),
            if (offline)
              Material(
                color: Colors.orange.shade800,
                child: const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  child: Text(
                    'Offline — scanning needs internet. Manual catalog search still works when cached.',
                    style: TextStyle(color: Colors.white, fontSize: 13),
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
            Expanded(child: _buildBody(scan, controller)),
            if (scan.errorMessage != null)
              Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    Text(
                      scan.errorMessage!,
                      style: const TextStyle(color: Colors.redAccent),
                      textAlign: TextAlign.center,
                    ),
                    TextButton(
                      onPressed: () =>
                          ref.read(scanControllerProvider.notifier).clearError(),
                      child: const Text('Dismiss'),
                    ),
                  ],
                ),
              ),
            _CaptureBar(
              busy: scan.isBusy,
              enabled: scan.isCameraReady && !scan.permissionDenied && !offline,
              onCapture: _onCapture,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBody(ScanUiState scan, CameraController? controller) {
    if (scan.permissionDenied) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Camera permission denied.\nOpen system settings, enable Camera for AmGold, then return here.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.white),
          ),
        ),
      );
    }
    if (scan.initError != null) {
      return Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                scan.initError!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: () =>
                    ref.read(scanControllerProvider.notifier).initCamera(),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }
    if (!scan.isCameraReady || controller == null) {
      return const Center(child: CircularProgressIndicator());
    }

    return LayoutBuilder(
      builder: (context, constraints) {
        return GestureDetector(
          onTapDown: (d) => _onTapPreview(d, constraints),
          child: Stack(
            fit: StackFit.expand,
            children: [
              Center(child: CameraPreview(controller)),
              ScanOverlay(scanning: scan.phase == ScanPhase.uploading),
            ],
          ),
        );
      },
    );
  }
}

class _CaptureBar extends StatelessWidget {
  const _CaptureBar({
    required this.busy,
    required this.enabled,
    required this.onCapture,
  });

  final bool busy;
  final bool enabled;
  final VoidCallback onCapture;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 20),
      child: Center(
        child: GestureDetector(
          onTap: enabled && !busy ? onCapture : null,
          child: Container(
            width: 76,
            height: 76,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white, width: 4),
              color: busy
                  ? Colors.white24
                  : (enabled ? AppColors.gold : Colors.white24),
            ),
            child: busy
                ? const Padding(
                    padding: EdgeInsets.all(20),
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.camera_alt, color: Colors.black87, size: 32),
          ),
        ),
      ),
    );
  }
}
