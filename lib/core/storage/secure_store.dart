// Secure persistence for device + session tokens (Android Keystore-backed).
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const _kDeviceToken = 'amgold_device_token';
const _kDeviceId = 'amgold_device_id';
const _kDeviceLabel = 'amgold_device_label';
const _kAccessToken = 'amgold_access_token';
const _kRefreshToken = 'amgold_refresh_token';
const _kUsername = 'amgold_username';
const _kDisplayName = 'amgold_display_name';
const _kUserRole = 'amgold_user_role';
const _kUserId = 'amgold_user_id';

class SecureStore {
  SecureStore({FlutterSecureStorage? storage})
      : _storage = storage ??
            const FlutterSecureStorage(
              // v10+: AES-GCM + RSA OAEP (encryptedSharedPreferences removed).
              aOptions: AndroidOptions(),
            );

  final FlutterSecureStorage _storage;

  Future<String?> read(String key) => _storage.read(key: key);

  Future<void> write(String key, String? value) async {
    if (value == null || value.isEmpty) {
      await _storage.delete(key: key);
    } else {
      await _storage.write(key: key, value: value);
    }
  }

  Future<String?> get deviceToken => read(_kDeviceToken);
  Future<String?> get deviceId => read(_kDeviceId);
  Future<String?> get deviceLabel => read(_kDeviceLabel);
  Future<String?> get accessToken => read(_kAccessToken);
  Future<String?> get refreshToken => read(_kRefreshToken);
  Future<String?> get username => read(_kUsername);
  Future<String?> get displayName => read(_kDisplayName);
  Future<String?> get userRole => read(_kUserRole);
  Future<String?> get userId => read(_kUserId);

  Future<bool> get isEnrolled async {
    final token = await deviceToken;
    return token != null && token.isNotEmpty;
  }

  Future<bool> get hasSession async {
    final access = await accessToken;
    final refresh = await refreshToken;
    return (access != null && access.isNotEmpty) ||
        (refresh != null && refresh.isNotEmpty);
  }

  Future<void> saveEnrollment({
    required String deviceId,
    required String deviceToken,
    required String label,
  }) async {
    await write(_kDeviceId, deviceId);
    await write(_kDeviceToken, deviceToken);
    await write(_kDeviceLabel, label);
  }

  Future<void> saveSession({
    required String accessToken,
    required String refreshToken,
    required String userId,
    required String username,
    required String displayName,
    required String role,
  }) async {
    await write(_kAccessToken, accessToken);
    await write(_kRefreshToken, refreshToken);
    await write(_kUserId, userId);
    await write(_kUsername, username);
    await write(_kDisplayName, displayName);
    await write(_kUserRole, role);
  }

  Future<void> clearSession() async {
    await write(_kAccessToken, null);
    await write(_kRefreshToken, null);
    await write(_kUserId, null);
    await write(_kUsername, null);
    await write(_kDisplayName, null);
    await write(_kUserRole, null);
  }

  /// Clears session and device binding (full logout / re-enroll).
  Future<void> clearAll() async {
    await clearSession();
    await write(_kDeviceToken, null);
    await write(_kDeviceId, null);
    await write(_kDeviceLabel, null);
  }
}

final secureStoreProvider = Provider<SecureStore>((ref) => SecureStore());
