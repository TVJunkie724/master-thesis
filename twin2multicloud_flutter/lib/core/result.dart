import 'package:dio/dio.dart';

/// Represents the result of an operation that can either succeed or fail.
/// 
/// Use pattern matching to handle both cases:
/// ```dart
/// switch (result) {
///   case Success(data: final value):
///     // Handle success
///   case Failure(error: final e):
///     // Handle error
/// }
/// ```
sealed class Result<T> {
  const Result();
  
  /// Returns true if this result is a success.
  bool get isSuccess => this is Success<T>;
  
  /// Returns true if this result is a failure.
  bool get isFailure => this is Failure<T>;
  
  /// Returns the data if success, null otherwise.
  T? get dataOrNull => switch (this) {
    Success(data: final d) => d,
    Failure() => null,
  };
}

/// Represents a successful result containing data.
class Success<T> extends Result<T> {
  final T data;
  const Success(this.data);
}

/// Represents a failed result containing an error.
class Failure<T> extends Result<T> {
  final AppException error;
  const Failure(this.error);
  
  /// Create a failure with just an error message.
  factory Failure.message(String message) => Failure(AppException(message));
}

/// Application-level exception with structured error information.
class AppException implements Exception {
  /// Human-readable error message suitable for display.
  final String message;
  
  /// Optional error code for programmatic handling (e.g., 'TIMEOUT', 'HTTP_404').
  final String? code;
  
  /// The original error that caused this exception.
  final dynamic originalError;
  
  const AppException(
    this.message, {
    this.code,
    this.originalError,
  });
  
  @override
  String toString() => code != null 
      ? 'AppException[$code]: $message' 
      : 'AppException: $message';
  
  /// Create an AppException from a DioException.
  factory AppException.fromDioError(DioException e) {
    return switch (e.type) {
      DioExceptionType.connectionTimeout => 
        const AppException('Connection timed out', code: 'TIMEOUT'),
      DioExceptionType.sendTimeout => 
        const AppException('Request timed out', code: 'TIMEOUT'),
      DioExceptionType.receiveTimeout => 
        const AppException('Server not responding', code: 'TIMEOUT'),
      DioExceptionType.badCertificate =>
        const AppException('Certificate error', code: 'CERT_ERROR'),
      DioExceptionType.connectionError =>
        const AppException('Could not connect to server', code: 'CONNECTION'),
      DioExceptionType.badResponse => _handleBadResponse(e),
      DioExceptionType.cancel =>
        const AppException('Request cancelled', code: 'CANCELLED'),
      DioExceptionType.unknown => 
        AppException('Network error: ${e.message}', originalError: e),
    };
  }
  
  static AppException _handleBadResponse(DioException e) {
    final statusCode = e.response?.statusCode ?? 0;
    final data = e.response?.data;
    
    // Extract detail message from FastAPI error responses
    String message;
    if (data is Map && data.containsKey('detail')) {
      message = data['detail'].toString();
    } else if (data is String) {
      message = data;
    } else {
      message = 'Server error ($statusCode)';
    }
    
    return AppException(
      message,
      code: 'HTTP_$statusCode',
      originalError: e,
    );
  }
}
