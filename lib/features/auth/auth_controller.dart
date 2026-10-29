// Auth state: enroll, PIN login, restore, logout.
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_exception.dart';
import '../../core/storage/secure_store.dart';
import '../../models/user.dart';

class AuthState {
  const AuthState({
    this.isLoading = true,
    this.isEnrolled = false,
    this.isLoggedIn = false,
    this.user,
    this.deviceId,
    this.deviceLabel,
    this.error,
  });

  final bool isLoading;
  final bool isEnrolled;
  final bool isLoggedIn;
  final AppUser? user;
  final String? deviceId;
  final String? deviceLabel;
  final String? error;

  AuthState copyWith({
    bool? isLoading,
    bool? isEnrolled,
    bool? isLoggedIn,
    AppUser? user,
    String? deviceId,
    String? deviceLabel,
    String? error,
    bool clearError = false,
    bool clearUser = false,
  }) {
    return AuthState(
      isLoading: isLoading ?? this.isLoading,
      isEnrolled: isEnrolled ?? this.isEnrolled,
      isLoggedIn: isLoggedIn ?? this.isLoggedIn,
      user: clearUser ? null : (user ?? this.user),
      deviceId: deviceId ?? this.deviceId,
      deviceLabel: deviceLabel ?? this.deviceLabel,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class AuthController extends Notifier<AuthState> {
  @override
  AuthState build() {
    Future.microtask(restore);
    return const AuthState(isLoading: true);
  }

  SecureStore get _store => ref.read(secureStoreProvider);
  ApiClient get _api => ref.read(apiClientProvider);

  Future<void> restore() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final enrolled = await _store.isEnrolled;
      final deviceId = await _store.deviceId;
      final deviceLabel = await _store.deviceLabel;
      final hasSession = await _store.hasSession;

      if (!enrolled) {
        state = const AuthState(
          isLoading: false,
          isEnrolled: false,
          isLoggedIn: false,
        );
        return;
      }

      if (!hasSession) {
        state = AuthState(
          isLoading: false,
          isEnrolled: true,
          isLoggedIn: false,
          deviceId: deviceId,
          deviceLabel: deviceLabel,
        );
        return;
      }

      try {
        final user = await _api.me();
        final access = await _store.accessToken;
        final refreshTok = await _store.refreshToken;
        if (access != null &&
            access.isNotEmpty &&
            refreshTok != null &&
            refreshTok.isNotEmpty) {
          await _store.saveSession(
            accessToken: access,
            refreshToken: refreshTok,
            userId: user.id,
            username: user.username,
            displayName: user.displayName,
            role: user.role,
          );
        }
        state = AuthState(
          isLoading: false,
          isEnrolled: true,
          isLoggedIn: true,
          user: user,
          deviceId: deviceId,
          deviceLabel: deviceLabel,
        );
      } on ApiException catch (e) {
        if (e.statusCode == 401) {
          final refreshTok = await _store.refreshToken;
          if (refreshTok != null && refreshTok.isNotEmpty) {
            try {
              final result = await _api.refresh(refreshToken: refreshTok);
              await _store.saveSession(
                accessToken: result.accessToken,
                refreshToken: result.refreshToken,
                userId: result.user.id,
                username: result.user.username,
                displayName: result.user.displayName,
                role: result.user.role,
              );
              state = AuthState(
                isLoading: false,
                isEnrolled: true,
                isLoggedIn: true,
                user: result.user,
                deviceId: deviceId,
                deviceLabel: deviceLabel,
              );
              return;
            } catch (_) {
              await _store.clearSession();
            }
          } else {
            await _store.clearSession();
          }
        }
        // Fall back to cached profile if network failed but tokens exist.
        final username = await _store.username;
        final displayName = await _store.displayName;
        final role = await _store.userRole;
        final userId = await _store.userId;
        if (username != null &&
            username.isNotEmpty &&
            userId != null &&
            e.statusCode != 401) {
          state = AuthState(
            isLoading: false,
            isEnrolled: true,
            isLoggedIn: true,
            user: AppUser(
              id: userId,
              username: username,
              displayName: displayName ?? username,
              role: role ?? 'staff',
            ),
            deviceId: deviceId,
            deviceLabel: deviceLabel,
          );
        } else {
          state = AuthState(
            isLoading: false,
            isEnrolled: true,
            isLoggedIn: false,
            deviceId: deviceId,
            deviceLabel: deviceLabel,
          );
        }
      }
    } catch (e) {
      state = AuthState(
        isLoading: false,
        error: e.toString(),
      );
    }
  }

  Future<bool> enroll({
    required String code,
    required String label,
    required String platform,
    required String appVersion,
  }) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final data = await _api.enrollDevice(
        code: code.trim(),
        label: label.trim().isEmpty ? 'Shop phone' : label.trim(),
        platform: platform,
        appVersion: appVersion,
      );
      final deviceId = data['device_id'].toString();
      final deviceToken = data['device_token'] as String;
      await _store.saveEnrollment(
        deviceId: deviceId,
        deviceToken: deviceToken,
        label: label.trim().isEmpty ? 'Shop phone' : label.trim(),
      );
      state = AuthState(
        isLoading: false,
        isEnrolled: true,
        isLoggedIn: false,
        deviceId: deviceId,
        deviceLabel: label.trim().isEmpty ? 'Shop phone' : label.trim(),
      );
      return true;
    } on ApiException catch (e) {
      state = state.copyWith(isLoading: false, error: e.message);
      return false;
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
      return false;
    }
  }

  Future<bool> login(String username, String pin) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final result = await _api.login(username: username.trim(), pin: pin);
      await _store.saveSession(
        accessToken: result.accessToken,
        refreshToken: result.refreshToken,
        userId: result.user.id,
        username: result.user.username,
        displayName: result.user.displayName,
        role: result.user.role,
      );
      final deviceId = await _store.deviceId;
      final deviceLabel = await _store.deviceLabel;
      state = AuthState(
        isLoading: false,
        isEnrolled: true,
        isLoggedIn: true,
        user: result.user,
        deviceId: deviceId,
        deviceLabel: deviceLabel,
      );
      return true;
    } on ApiException catch (e) {
      state = state.copyWith(isLoading: false, error: e.message);
      return false;
    } catch (e) {
      state = state.copyWith(isLoading: false, error: e.toString());
      return false;
    }
  }

  Future<void> logout({bool clearDevice = false}) async {
    if (clearDevice) {
      await _store.clearAll();
      state = const AuthState(isLoading: false, isEnrolled: false, isLoggedIn: false);
    } else {
      await _store.clearSession();
      final deviceId = await _store.deviceId;
      final deviceLabel = await _store.deviceLabel;
      state = AuthState(
        isLoading: false,
        isEnrolled: true,
        isLoggedIn: false,
        deviceId: deviceId,
        deviceLabel: deviceLabel,
      );
    }
  }
}

final authControllerProvider =
    NotifierProvider<AuthController, AuthState>(AuthController.new);
