// Dio client for /v1: Bearer JWT + X-Device-Token, refresh on 401.
import 'dart:async';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/bill_draft_remote.dart';
import '../../models/product.dart';
import '../../models/scan_result.dart';
import '../../models/user.dart';
import '../config/app_config.dart';
import '../storage/secure_store.dart';
import 'api_exception.dart';

final apiClientProvider = Provider<ApiClient>((ref) {
  final store = ref.watch(secureStoreProvider);
  return ApiClient(
    baseUrl: AppConfig.apiBaseUrl,
    store: store,
  );
});

class ApiClient {
  ApiClient({
    required String baseUrl,
    required SecureStore store,
    Dio? dio,
  })  : _store = store, // ignore: prefer_initializing_formals
        _baseUrl = baseUrl.replaceAll(RegExp(r'/$'), ''),
        _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: baseUrl.isEmpty ? 'https://invalid.local' : baseUrl,
                connectTimeout: const Duration(seconds: 25),
                receiveTimeout: const Duration(seconds: 25),
                sendTimeout: const Duration(seconds: 25),
                headers: {'Accept': 'application/json'},
              ),
            ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          if (!_skipAuth(options.path)) {
            final device = await _store.deviceToken;
            final access = await _store.accessToken;
            if (device != null && device.isNotEmpty) {
              options.headers['X-Device-Token'] = device;
            }
            if (access != null && access.isNotEmpty) {
              options.headers['Authorization'] = 'Bearer $access';
            }
          }
          handler.next(options);
        },
        onError: (error, handler) async {
          final status = error.response?.statusCode;
          final req = error.requestOptions;
          final alreadyRetried = req.extra['amgold_retried'] == true;
          if (status == 401 &&
              !alreadyRetried &&
              !_skipAuth(req.path) &&
              !_isRefreshPath(req.path)) {
            try {
              await _refreshTokens();
              final device = await _store.deviceToken;
              final access = await _store.accessToken;
              if (device != null) {
                req.headers['X-Device-Token'] = device;
              }
              if (access != null) {
                req.headers['Authorization'] = 'Bearer $access';
              }
              req.extra['amgold_retried'] = true;
              final response = await _dio.fetch<dynamic>(req);
              return handler.resolve(response);
            } catch (_) {
              return handler.next(error);
            }
          }
          handler.next(error);
        },
      ),
    );
  }

  final String _baseUrl;
  final SecureStore _store;
  final Dio _dio;
  Completer<void>? _refreshLock;

  Dio get dio => _dio;

  bool _skipAuth(String path) {
    return path.contains('/health') || path.contains('/devices/enroll');
  }

  bool _isRefreshPath(String path) => path.contains('/auth/refresh');

  /// Resolves a product photo path or absolute URL for CachedNetworkImage.
  String? resolvePhotoUrl(String? pathOrUrl) {
    if (pathOrUrl == null || pathOrUrl.isEmpty) return null;
    if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) {
      return pathOrUrl;
    }
    if (_baseUrl.isEmpty) return pathOrUrl;
    if (pathOrUrl.startsWith('/')) return '$_baseUrl$pathOrUrl';
    return '$_baseUrl/$pathOrUrl';
  }

  @Deprecated('Use resolvePhotoUrl')
  String photoUrl(String relativePath) =>
      resolvePhotoUrl(relativePath) ?? relativePath;

  Future<Map<String, dynamic>> enrollDevice({
    required String code,
    required String label,
    required String platform,
    required String appVersion,
  }) async {
    final response = await _withRetry(
      () => _dio.post<Map<String, dynamic>>(
        '/v1/devices/enroll',
        data: {
          'code': code,
          'label': label,
          'platform': platform,
          'app_version': appVersion,
        },
      ),
    );
    return response.data ?? {};
  }

  Future<({String accessToken, String refreshToken, int expiresIn, AppUser user})>
      login({
    required String username,
    required String pin,
  }) async {
    final device = await _store.deviceToken;
    final response = await _withRetry(
      () => _dio.post<Map<String, dynamic>>(
        '/v1/auth/login',
        data: {'username': username, 'pin': pin},
        options: Options(
          headers: {
            'X-Device-Token': ?device,
          },
        ),
      ),
    );
    return _parseLogin(response.data);
  }

  Future<({String accessToken, String refreshToken, int expiresIn, AppUser user})>
      refresh({required String refreshToken}) async {
    final device = await _store.deviceToken;
    final response = await _dio.post<Map<String, dynamic>>(
      '/v1/auth/refresh',
      data: {'refresh_token': refreshToken},
      options: Options(
        headers: {
          'X-Device-Token': ?device,
        },
      ),
    );
    return _parseLogin(response.data);
  }

  Future<AppUser> me() async {
    final response = await _withRetry(
      () => _dio.get<Map<String, dynamic>>('/v1/me'),
    );
    final data = response.data;
    if (data == null) throw ApiException('Empty /v1/me response');
    return AppUser.fromJson(data);
  }

  Future<bool> healthOk() async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        '/health',
        options: Options(
          sendTimeout: const Duration(seconds: 8),
          receiveTimeout: const Duration(seconds: 8),
        ),
      );
      return response.data?['ok'] == true;
    } catch (_) {
      return false;
    }
  }

  Future<ScanResult> scanImage(
    List<int> bytes, {
    String filename = 'scan.jpg',
  }) async {
    final form = FormData.fromMap({
      'image': MultipartFile.fromBytes(bytes, filename: filename),
    });
    final response = await _withRetry(
      () => _dio.post<Map<String, dynamic>>(
        '/v1/scan',
        data: form,
        options: Options(contentType: 'multipart/form-data'),
      ),
    );
    final data = response.data;
    if (data == null) throw ApiException('Empty response from /v1/scan');
    return ScanResult.fromJson(data);
  }

  Future<void> sendScanFeedback({
    required String scanId,
    required String chosenProductId,
  }) async {
    await _withRetry(
      () => _dio.post<Map<String, dynamic>>(
        '/v1/scan/$scanId/feedback',
        data: {'chosen_product_id': chosenProductId},
      ),
    );
  }

  Future<({List<Product> items, String? nextCursor})> listProducts({
    String? q,
    String? category,
    int limit = 50,
    String? cursor,
  }) async {
    final response = await _withRetry(
      () => _dio.get<Map<String, dynamic>>(
        '/v1/products',
        queryParameters: {
          if (q != null && q.isNotEmpty) 'q': q,
          if (category != null && category.isNotEmpty) 'category': category,
          'limit': limit,
          if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
        },
      ),
    );
    final data = response.data ?? {};
    final items = (data['items'] as List<dynamic>? ?? const [])
        .map((e) => Product.fromJson(e as Map<String, dynamic>))
        .toList();
    return (items: items, nextCursor: data['next_cursor'] as String?);
  }

  Future<Product> getProduct(String id) async {
    final response = await _withRetry(
      () => _dio.get<Map<String, dynamic>>('/v1/products/$id'),
    );
    final data = response.data;
    if (data == null) throw ApiException('Empty product response');
    return Product.fromJson(data);
  }

  /// Owner: create product with reference photos (searchable immediately).
  Future<({Product product, List<String> photoIds, List<dynamic> warnings})>
      createProduct({
    required String name,
    required String category,
    required String price,
    String material = 'rolled_gold',
    String? weightG,
    String? description,
    String? differenceNote,
    String unit = 'pcs',
    String? code,
    required List<Uint8List> photoBytes,
  }) async {
    if (photoBytes.isEmpty) {
      throw ApiException('Add at least one photo before saving.');
    }
    final form = FormData();
    form.fields.addAll([
      MapEntry('name', name),
      MapEntry('category', category),
      MapEntry('price', price),
      MapEntry('material', material),
      MapEntry('unit', unit),
      if (weightG != null && weightG.isNotEmpty) MapEntry('weight_g', weightG),
      if (description != null && description.isNotEmpty)
        MapEntry('description', description),
      if (differenceNote != null && differenceNote.isNotEmpty)
        MapEntry('difference_note', differenceNote),
      if (code != null && code.isNotEmpty) MapEntry('code', code),
    ]);
    for (var i = 0; i < photoBytes.length; i++) {
      form.files.add(
        MapEntry(
          'photos',
          MultipartFile.fromBytes(
            photoBytes[i],
            filename: 'photo_$i.jpg',
          ),
        ),
      );
    }

    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/v1/products',
        data: form,
        options: Options(
          contentType: 'multipart/form-data',
          sendTimeout: const Duration(minutes: 2),
          receiveTimeout: const Duration(minutes: 2),
        ),
      );
      final data = response.data;
      if (data == null) throw ApiException('Empty response from create product');
      final productRaw = data['product'];
      if (productRaw is! Map<String, dynamic>) {
        throw ApiException('Invalid product in create response');
      }
      final ids = (data['photo_ids'] as List<dynamic>? ?? const [])
          .map((e) => e.toString())
          .toList();
      final warnings = data['photo_warnings'] as List<dynamic>? ?? const [];
      return (
        product: Product.fromJson(productRaw),
        photoIds: ids,
        warnings: warnings,
      );
    } on DioException catch (e) {
      throw _mapDio(e);
    }
  }

  Future<BillDraftRemote> createBillDraft({
    required String clientDraftId,
    String? customerName,
    String? customerPhone,
    String? notes,
    double? discountAmount,
    required List<Map<String, dynamic>> items,
  }) async {
    final response = await _withRetry(
      () => _dio.post<Map<String, dynamic>>(
        '/v1/bills/drafts',
        data: {
          'client_draft_id': clientDraftId,
          if (customerName != null && customerName.isNotEmpty)
            'customer_name': customerName,
          if (customerPhone != null && customerPhone.isNotEmpty)
            'customer_phone': customerPhone,
          if (notes != null && notes.isNotEmpty) 'notes': notes,
          if (discountAmount != null && discountAmount > 0)
            'discount_amount': discountAmount,
          'items': items,
        },
      ),
    );
    final data = response.data;
    if (data == null) throw ApiException('Empty draft response');
    return BillDraftRemote.fromJson(data);
  }

  Future<List<BillDraftRemote>> listBillDrafts({int limit = 50}) async {
    final response = await _withRetry(
      () => _dio.get<dynamic>(
        '/v1/bills/drafts',
        queryParameters: {'limit': limit},
      ),
    );
    final raw = response.data;
    final list = raw is List ? raw : const [];
    return list.map((e) {
      if (e is Map<String, dynamic>) return BillDraftRemote.fromJson(e);
      if (e is Map) {
        return BillDraftRemote.fromJson(Map<String, dynamic>.from(e));
      }
      throw ApiException('Unexpected draft list entry');
    }).toList();
  }

  Future<void> _refreshTokens() async {
    if (_refreshLock != null) {
      await _refreshLock!.future;
      return;
    }
    final lock = Completer<void>();
    _refreshLock = lock;
    try {
      final refreshTok = await _store.refreshToken;
      if (refreshTok == null || refreshTok.isEmpty) {
        throw ApiException('Session expired. Please sign in again.', statusCode: 401);
      }
      final result = await refresh(refreshToken: refreshTok);
      await _store.saveSession(
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
        userId: result.user.id,
        username: result.user.username,
        displayName: result.user.displayName,
        role: result.user.role,
      );
      lock.complete();
    } catch (e) {
      lock.completeError(e);
      rethrow;
    } finally {
      _refreshLock = null;
    }
  }

  ({String accessToken, String refreshToken, int expiresIn, AppUser user})
      _parseLogin(Map<String, dynamic>? data) {
    if (data == null) throw ApiException('Empty auth response');
    final userRaw = data['user'];
    if (userRaw is! Map<String, dynamic>) {
      throw ApiException('Auth response missing user');
    }
    return (
      accessToken: data['access_token'] as String,
      refreshToken: data['refresh_token'] as String,
      expiresIn: data['expires_in'] as int? ?? 0,
      user: AppUser.fromJson(userRaw),
    );
  }

  Future<Response<T>> _withRetry<T>(
    Future<Response<T>> Function() action,
  ) async {
    if (!AppConfig.hasApiBaseUrl) {
      throw ApiException(
        'API_BASE_URL is not set. Rebuild with --dart-define=API_BASE_URL=https://...',
      );
    }
    try {
      return await action();
    } on DioException catch (first) {
      if (!_isRetryable(first)) {
        throw _mapDio(first);
      }
      try {
        return await action();
      } on DioException catch (second) {
        throw _mapDio(second);
      }
    }
  }

  bool _isRetryable(DioException e) {
    return e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout;
  }

  ApiException _mapDio(DioException e) {
    final status = e.response?.statusCode;
    final detail = e.response?.data;
    String message;
    if (detail is Map && detail['detail'] is String) {
      message = detail['detail'] as String;
    } else if (status == 401) {
      message = 'Session expired or device not approved. Sign in again.';
    } else if (status == 403) {
      message = 'Not allowed for this account or device.';
    } else if (status == 429) {
      message = 'Too many attempts. Wait a moment and try again.';
    } else if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout) {
      message = 'Request timed out. Check your connection.';
    } else if (e.type == DioExceptionType.connectionError) {
      message = 'Cannot reach the server. Check internet and API_BASE_URL.';
    } else {
      message = e.message ?? 'Network error';
    }
    return ApiException(message, statusCode: status, cause: e);
  }
}
