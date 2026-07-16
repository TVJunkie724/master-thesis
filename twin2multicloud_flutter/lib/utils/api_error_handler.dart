import 'package:dio/dio.dart';

import '../core/result.dart';

/// Utility for extracting user-friendly error messages from API responses.
///
/// This handles various error scenarios:
/// - DioException with structured JSON error response (detail, message, error)
/// - Connection timeouts and network errors
/// - Explicitly user-facing application exceptions
/// - Neutral fallback for all unexpected exceptions
class ApiErrorHandler {
  /// Extract a user-friendly error message from any exception.
  ///
  /// Priority for DioException responses:
  /// 1. response.data['detail'] (FastAPI standard)
  /// 2. response.data['message'] (common alternative)
  /// 3. response.data['error'] (fallback)
  /// 4. Connection-specific messages
  /// 5. Generic fallback
  static String extractMessage(dynamic error) {
    if (error is UserFacingException) {
      return error.message;
    }

    if (error is DioException) {
      return _handleDioException(error);
    }

    return 'An unexpected error occurred';
  }

  static String _handleDioException(DioException error) {
    // Try to extract message from response body
    final response = error.response;
    if (response != null) {
      final data = response.data;

      if (data is Map<String, dynamic>) {
        // FastAPI returns errors in 'detail' field
        if (data.containsKey('detail')) {
          final detail = data['detail'];
          if (detail is String) {
            return detail;
          } else if (detail is List && detail.isNotEmpty) {
            // Pydantic validation errors
            return detail.map((e) => e['msg'] ?? e.toString()).join(', ');
          } else if (detail is Map) {
            final message = detail['message']?.toString().trim();
            final errors = detail['errors'];
            final errorMessages = errors is List
                ? errors
                      .whereType<Map>()
                      .map((item) => item['message']?.toString().trim())
                      .whereType<String>()
                      .where((item) => item.isNotEmpty)
                      .toList(growable: false)
                : const <String>[];
            if (message?.isNotEmpty == true) {
              return errorMessages.isEmpty
                  ? message!
                  : '$message: ${errorMessages.join('; ')}';
            }
            if (errorMessages.isNotEmpty) return errorMessages.join('; ');
          }
        }

        // Alternative error fields
        if (data.containsKey('message')) {
          return data['message'].toString();
        }
        if (data.containsKey('error')) {
          return data['error'].toString();
        }
      }

      // If response is a plain string
      if (data is String && data.isNotEmpty) {
        return data;
      }

      // Fallback to status message
      if (response.statusMessage != null &&
          response.statusMessage!.isNotEmpty) {
        return 'Server error: ${response.statusMessage}';
      }
    }

    // Handle specific DioException types
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
        return 'Connection timed out. Please check your network.';
      case DioExceptionType.sendTimeout:
        return 'Request timed out while sending data.';
      case DioExceptionType.receiveTimeout:
        return 'Response timed out. The server may be busy.';
      case DioExceptionType.transformTimeout:
        return 'Response processing timed out. Please try again.';
      case DioExceptionType.connectionError:
        return 'Cannot connect to server. Please check if the service is running.';
      case DioExceptionType.badCertificate:
        return 'SSL certificate error. Please contact support.';
      case DioExceptionType.badResponse:
        final statusCode = error.response?.statusCode;
        if (statusCode != null) {
          return _getStatusCodeMessage(statusCode);
        }
        return 'Server returned an invalid response.';
      case DioExceptionType.cancel:
        return 'Request was cancelled.';
      case DioExceptionType.unknown:
        if (error.message?.contains('SocketException') == true) {
          return 'Cannot connect to server. Please check your network.';
        }
        return 'An unexpected network error occurred.';
    }
  }

  static String _getStatusCodeMessage(int statusCode) {
    switch (statusCode) {
      case 400:
        return 'Invalid request. Please check your input.';
      case 401:
        return 'Authentication required. Please log in.';
      case 403:
        return 'Access denied. You do not have permission.';
      case 404:
        return 'Resource not found.';
      case 408:
        return 'Request timeout. Please try again.';
      case 429:
        return 'Too many requests. Please wait and try again.';
      case 500:
        return 'Server error. Please try again later.';
      case 502:
        return 'Bad gateway. The server may be temporarily unavailable.';
      case 503:
        return 'Service unavailable. Please try again later.';
      case 504:
        return 'Gateway timeout. The server took too long to respond.';
      default:
        if (statusCode >= 400 && statusCode < 500) {
          return 'Request error ($statusCode).';
        } else if (statusCode >= 500) {
          return 'Server error ($statusCode).';
        }
        return 'Unexpected response ($statusCode).';
    }
  }
}
