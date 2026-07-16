import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/utils/api_error_handler.dart';

void main() {
  test('does not expose arbitrary exception details', () {
    final error = Exception('credential=must-not-leak');

    expect(
      ApiErrorHandler.extractMessage(error),
      'An unexpected error occurred',
    );
  });

  test('retains explicitly user-facing application messages', () {
    const error = AppException('The selected connection is still in use.');

    expect(
      ApiErrorHandler.extractMessage(error),
      'The selected connection is still in use.',
    );
  });

  test('maps response transformation timeouts to a retryable message', () {
    final error = DioException(
      requestOptions: RequestOptions(path: '/twins'),
      type: DioExceptionType.transformTimeout,
    );

    expect(
      ApiErrorHandler.extractMessage(error),
      'Response processing timed out. Please try again.',
    );
  });

  test('extracts structured distributed validation errors', () {
    final error = DioException(
      requestOptions: RequestOptions(path: '/twins/twin-1'),
      response: Response<Map<String, dynamic>>(
        requestOptions: RequestOptions(path: '/twins/twin-1'),
        statusCode: 400,
        data: {
          'detail': {
            'code': 'VALIDATION_FAILED',
            'message': 'Cannot mark as configured: 2 validation errors',
            'errors': [
              {'field': 'credentials', 'message': 'AWS access is missing'},
              {'field': 'payloads', 'message': 'Payload schema is invalid'},
            ],
          },
        },
      ),
      type: DioExceptionType.badResponse,
    );

    expect(
      ApiErrorHandler.extractMessage(error),
      'Cannot mark as configured: 2 validation errors: AWS access is missing; Payload schema is invalid',
    );
  });
}
