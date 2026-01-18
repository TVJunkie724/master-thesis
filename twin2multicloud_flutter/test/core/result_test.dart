import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/core/result.dart';

void main() {
  group('Result', () {
    // ============================================================
    // Happy Path Tests
    // ============================================================

    group('Success', () {
      test('isSuccess returns true', () {
        final result = Success<int>(42);
        
        expect(result.isSuccess, isTrue);
        expect(result.isFailure, isFalse);
      });

      test('dataOrNull returns data', () {
        final result = Success<String>('hello');
        
        expect(result.dataOrNull, 'hello');
      });

      test('pattern matching extracts data', () {
        final Result<int> result = Success(42);
        
        final value = switch (result) {
          Success(data: final d) => d,
          Failure() => -1,
        };
        
        expect(value, 42);
      });
    });

    group('Failure', () {
      test('isFailure returns true', () {
        final result = Failure<int>(const AppException('error'));
        
        expect(result.isFailure, isTrue);
        expect(result.isSuccess, isFalse);
      });

      test('dataOrNull returns null', () {
        final result = Failure<String>(const AppException('error'));
        
        expect(result.dataOrNull, isNull);
      });

      test('Failure.message factory creates instance', () {
        final result = Failure<int>.message('Something went wrong');
        
        expect(result.error.message, 'Something went wrong');
      });

      test('pattern matching extracts error', () {
        final Result<int> result = Failure(const AppException('oops'));
        
        final message = switch (result) {
          Success() => 'success',
          Failure(error: final e) => e.message,
        };
        
        expect(message, 'oops');
      });
    });
  });

  group('AppException', () {
    // ============================================================
    // Happy Path Tests
    // ============================================================

    group('construction', () {
      test('creates with message only', () {
        const error = AppException('Something failed');
        
        expect(error.message, 'Something failed');
        expect(error.code, isNull);
        expect(error.originalError, isNull);
      });

      test('creates with all fields', () {
        final original = Exception('original');
        final error = AppException(
          'Wrapped error',
          code: 'ERR_001',
          originalError: original,
        );
        
        expect(error.message, 'Wrapped error');
        expect(error.code, 'ERR_001');
        expect(error.originalError, original);
      });

      test('toString includes code when present', () {
        const error = AppException('Failed', code: 'HTTP_404');
        
        expect(error.toString(), contains('HTTP_404'));
        expect(error.toString(), contains('Failed'));
      });
    });

    // ============================================================
    // Error Case Tests - DioException Conversion
    // ============================================================

    group('fromDioError', () {
      test('handles connectionTimeout', () {
        final dioError = DioException(
          type: DioExceptionType.connectionTimeout,
          requestOptions: RequestOptions(path: '/test'),
        );
        
        final error = AppException.fromDioError(dioError);
        
        expect(error.code, 'TIMEOUT');
        expect(error.message, contains('timed out'));
      });

      test('handles receiveTimeout', () {
        final dioError = DioException(
          type: DioExceptionType.receiveTimeout,
          requestOptions: RequestOptions(path: '/test'),
        );
        
        final error = AppException.fromDioError(dioError);
        
        expect(error.code, 'TIMEOUT');
        expect(error.message, contains('not responding'));
      });

      test('handles connectionError', () {
        final dioError = DioException(
          type: DioExceptionType.connectionError,
          requestOptions: RequestOptions(path: '/test'),
        );
        
        final error = AppException.fromDioError(dioError);
        
        expect(error.code, 'CONNECTION');
        expect(error.message, contains('connect'));
      });

      test('handles badResponse with status code', () {
        final dioError = DioException(
          type: DioExceptionType.badResponse,
          response: Response(
            statusCode: 404,
            requestOptions: RequestOptions(path: '/test'),
          ),
          requestOptions: RequestOptions(path: '/test'),
        );
        
        final error = AppException.fromDioError(dioError);
        
        expect(error.code, 'HTTP_404');
      });

      test('extracts detail from FastAPI error response', () {
        final dioError = DioException(
          type: DioExceptionType.badResponse,
          response: Response(
            statusCode: 422,
            data: {'detail': 'Validation failed'},
            requestOptions: RequestOptions(path: '/test'),
          ),
          requestOptions: RequestOptions(path: '/test'),
        );
        
        final error = AppException.fromDioError(dioError);
        
        expect(error.message, 'Validation failed');
        expect(error.code, 'HTTP_422');
      });

      test('handles cancel', () {
        final dioError = DioException(
          type: DioExceptionType.cancel,
          requestOptions: RequestOptions(path: '/test'),
        );
        
        final error = AppException.fromDioError(dioError);
        
        expect(error.code, 'CANCELLED');
      });

      test('handles unknown error type', () {
        final dioError = DioException(
          type: DioExceptionType.unknown,
          message: 'Something weird happened',
          requestOptions: RequestOptions(path: '/test'),
        );
        
        final error = AppException.fromDioError(dioError);
        
        expect(error.message, contains('Network error'));
        expect(error.originalError, dioError);
      });
    });
  });
}
