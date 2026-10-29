// Production config: API_BASE_URL from --dart-define only.
class AppConfig {
  AppConfig._();

  /// Production HTTPS base URL. Pass at build time:
  /// `--dart-define=API_BASE_URL=https://your-service.up.railway.app`
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: '',
  );

  static bool get hasApiBaseUrl => apiBaseUrl.trim().isNotEmpty;

  static bool get isReleaseMode {
    var release = true;
    assert(() {
      release = false;
      return true;
    }());
    return release;
  }
}
