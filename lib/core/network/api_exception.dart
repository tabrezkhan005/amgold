// Typed API errors with user-friendly messages.
class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.cause, this.code});

  final String message;
  final int? statusCode;
  final String? code;
  final Object? cause;

  @override
  String toString() => 'ApiException($statusCode): $message';

  static ApiException fromDio(Object error) {
    return ApiException(
      'Could not reach the server. Check internet and API_BASE_URL.',
      cause: error,
    );
  }
}
