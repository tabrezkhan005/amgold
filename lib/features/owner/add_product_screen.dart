// Owner: capture reference photos + details → POST /v1/products.
import 'dart:io';
import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_colors.dart';
import '../../core/utils/haptics.dart';
import '../../core/utils/image_compress.dart';
import '../../widgets/primary_button.dart';
import '../../widgets/safe_camera_preview.dart';

const _categories = <String>[
  'necklace',
  'chain',
  'earring',
  'bangle',
  'ring',
  'pendant',
  'other',
];

const _minPhotos = 3;
const _idealPhotos = 5;
const _maxPhotos = 10;

class AddProductScreen extends ConsumerStatefulWidget {
  const AddProductScreen({super.key});

  @override
  ConsumerState<AddProductScreen> createState() => _AddProductScreenState();
}

class _AddProductScreenState extends ConsumerState<AddProductScreen> {
  final _pageCtrl = PageController();
  final _nameCtrl = TextEditingController();
  final _priceCtrl = TextEditingController();
  final _weightCtrl = TextEditingController();
  final _descCtrl = TextEditingController();
  final _diffCtrl = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  CameraController? _camera;
  bool _cameraReady = false;
  String? _cameraError;
  bool _capturing = false;
  bool _saving = false;
  String _saveStatus = '';
  String? _saveError;

  final List<String> _photoPaths = [];
  String _category = 'necklace';
  int _step = 0;

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  @override
  void dispose() {
    _pageCtrl.dispose();
    _nameCtrl.dispose();
    _priceCtrl.dispose();
    _weightCtrl.dispose();
    _descCtrl.dispose();
    _diffCtrl.dispose();
    _disposeCamera();
    super.dispose();
  }

  Future<void> _disposeCamera() async {
    final c = _camera;
    _camera = null;
    _cameraReady = false;
    if (c != null) {
      try {
        await c.dispose();
      } catch (_) {}
    }
  }

  Future<void> _initCamera() async {
    await _disposeCamera();
    if (!mounted) return;
    setState(() {
      _cameraError = null;
      _cameraReady = false;
    });
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        setState(() => _cameraError = 'No camera found on this device.');
        return;
      }
      final back = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      final controller = CameraController(
        back,
        ResolutionPreset.high,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );
      await controller.initialize();
      for (var i = 0; i < 40 && controller.value.previewSize == null; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 50));
      }
      if (!mounted) {
        await controller.dispose();
        return;
      }
      if (controller.value.previewSize == null) {
        await controller.dispose();
        setState(() =>
            _cameraError = 'Camera preview not ready. Tap Retry.');
        return;
      }
      _camera = controller;
      setState(() => _cameraReady = true);
    } on CameraException catch (e) {
      setState(() => _cameraError = e.description ?? e.code);
    } catch (e) {
      setState(() => _cameraError = e.toString());
    }
  }

  Future<void> _capture() async {
    final c = _camera;
    if (c == null ||
        !_cameraReady ||
        _capturing ||
        _photoPaths.length >= _maxPhotos) {
      return;
    }
    setState(() => _capturing = true);
    try {
      await hapticCapture();
      final shot = await c.takePicture();
      if (!mounted) return;
      setState(() => _photoPaths.add(shot.path));
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Capture failed: $e')),
      );
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  void _removePhoto(int index) {
    setState(() => _photoPaths.removeAt(index));
  }

  void _goDetails() {
    if (_photoPaths.length < _minPhotos) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Take at least $_minPhotos photos (5+ recommended).'),
        ),
      );
      return;
    }
    if (_photoPaths.length < _idealPhotos) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Tip: 5–8 angles work best for look-alikes.'),
        ),
      );
    }
    setState(() => _step = 1);
    _pageCtrl.animateToPage(
      1,
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeOut,
    );
  }

  Future<void> _save() async {
    final form = _formKey.currentState;
    if (form == null || !form.validate()) return;
    if (_photoPaths.length < _minPhotos) return;

    setState(() {
      _saving = true;
      _saveError = null;
      _saveStatus = 'Compressing ${_photoPaths.length} photos…';
    });

    try {
      final bytes = <Uint8List>[];
      for (var i = 0; i < _photoPaths.length; i++) {
        if (!mounted) return;
        setState(() =>
            _saveStatus = 'Compressing photo ${i + 1}/${_photoPaths.length}…');
        bytes.add(await compressScanImage(_photoPaths[i]));
      }
      if (!mounted) return;
      setState(() => _saveStatus =
          'Uploading & embedding ${_photoPaths.length} photos on server…\n'
          'This can take 15–60s (DINOv2 per photo).');
      final result = await ref.read(apiClientProvider).createProduct(
            name: _nameCtrl.text.trim(),
            category: _category,
            price: _priceCtrl.text.trim(),
            material: 'rolled_gold',
            weightG: _weightCtrl.text.trim().isEmpty
                ? null
                : _weightCtrl.text.trim(),
            description: _descCtrl.text.trim().isEmpty
                ? null
                : _descCtrl.text.trim(),
            differenceNote: _diffCtrl.text.trim().isEmpty
                ? null
                : _diffCtrl.text.trim(),
            photoBytes: bytes,
          );

      if (!mounted) return;
      final code = result.product.code;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Saved $code with ${result.photoIds.length} photos. '
            'Scan it once to verify.',
          ),
        ),
      );
      context.go('/product/${result.product.id}');
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _saveError = e.message);
    } catch (e) {
      if (!mounted) return;
      setState(() => _saveError = e.toString());
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_step == 0 ? 'Add product · Photos' : 'Add product · Details'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
      ),
      body: PageView(
        controller: _pageCtrl,
        physics: const NeverScrollableScrollPhysics(),
        children: [
          _buildCaptureStep(),
          _buildDetailsStep(),
        ],
      ),
    );
  }

  Widget _buildCaptureStep() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
          child: Text(
            'Capture $_minPhotos–$_maxPhotos angles (front, back/clasp, '
            'detail, angled, flat). Aim for 7–8 for look-alikes.',
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ),
        Expanded(child: _buildCameraArea()),
        if (_photoPaths.isNotEmpty)
          SizedBox(
            height: 88,
            child: ListView.separated(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              scrollDirection: Axis.horizontal,
              itemCount: _photoPaths.length,
              separatorBuilder: (_, _) => const SizedBox(width: 8),
              itemBuilder: (context, i) {
                return Stack(
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: Image.file(
                        File(_photoPaths[i]),
                        width: 72,
                        height: 72,
                        fit: BoxFit.cover,
                      ),
                    ),
                    Positioned(
                      top: 0,
                      right: 0,
                      child: InkWell(
                        onTap: () => _removePhoto(i),
                        child: const CircleAvatar(
                          radius: 12,
                          backgroundColor: Colors.black54,
                          child: Icon(Icons.close, size: 14, color: Colors.white),
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 20),
          child: Row(
            children: [
              Text(
                '${_photoPaths.length}/$_maxPhotos',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Spacer(),
              FilledButton.tonal(
                onPressed: _capturing ||
                        !_cameraReady ||
                        _photoPaths.length >= _maxPhotos
                    ? null
                    : _capture,
                child: Text(_capturing ? '…' : 'Capture'),
              ),
              const SizedBox(width: 12),
              FilledButton(
                onPressed: _photoPaths.length >= _minPhotos ? _goDetails : null,
                child: const Text('Next'),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildCameraArea() {
    if (_cameraError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_cameraError!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _initCamera,
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }
    final c = _camera;
    if (!_cameraReady || c == null) {
      return const Center(child: CircularProgressIndicator());
    }
    return ColoredBox(
      color: Colors.black,
      child: Center(child: SafeCameraPreview(c)),
    );
  }

  Widget _buildDetailsStep() {
    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          TextFormField(
            controller: _nameCtrl,
            textCapitalization: TextCapitalization.words,
            decoration: const InputDecoration(
              labelText: 'Name',
              border: OutlineInputBorder(),
            ),
            validator: (v) =>
                (v == null || v.trim().isEmpty) ? 'Required' : null,
          ),
          const SizedBox(height: 16),
          InputDecorator(
            decoration: const InputDecoration(
              labelText: 'Category',
              border: OutlineInputBorder(),
            ),
            child: DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                isExpanded: true,
                value: _category,
                items: [
                  for (final c in _categories)
                    DropdownMenuItem(value: c, child: Text(c)),
                ],
                onChanged: (v) {
                  if (v != null) setState(() => _category = v);
                },
              ),
            ),
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _priceCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Price (₹)',
              border: OutlineInputBorder(),
            ),
            validator: (v) {
              if (v == null || v.trim().isEmpty) return 'Required';
              final n = double.tryParse(v.trim());
              if (n == null || n < 0) return 'Enter a valid price';
              return null;
            },
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _weightCtrl,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              labelText: 'Weight (g) · optional',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          const Text(
            'Material is always shown as Rolled gold (not real gold).',
            style: TextStyle(color: AppColors.gold),
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _diffCtrl,
            decoration: const InputDecoration(
              labelText: 'Difference note (e.g. 8 beads) · optional',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 16),
          TextFormField(
            controller: _descCtrl,
            maxLines: 3,
            decoration: const InputDecoration(
              labelText: 'Description · optional',
              border: OutlineInputBorder(),
            ),
          ),
          if (_saving && _saveStatus.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(_saveStatus, style: Theme.of(context).textTheme.bodyMedium),
          ],
          if (_saveError != null) ...[
            const SizedBox(height: 12),
            Text(
              _saveError!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
          const SizedBox(height: 24),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: _saving
                      ? null
                      : () {
                          setState(() => _step = 0);
                          _pageCtrl.animateToPage(
                            0,
                            duration: const Duration(milliseconds: 250),
                            curve: Curves.easeOut,
                          );
                        },
                  child: const Text('Back'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: PrimaryButton(
                  label: 'Save product',
                  loading: _saving,
                  onPressed: _saving ? null : _save,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
