import 'dart:collection';

/// Secret-safe JSON contract decoding for Management API response models.
///
/// Errors identify the invalid field without including response values.
abstract final class JsonContract {
  static String requiredString(Map<String, dynamic> json, String field) {
    final value = json[field];
    if (value is! String || value.trim().isEmpty) {
      throw FormatException('Invalid API contract: $field must be a string.');
    }
    return value;
  }

  static String? optionalString(Map<String, dynamic> json, String field) {
    final value = json[field];
    if (value == null) return null;
    if (value is! String) {
      throw FormatException('Invalid API contract: $field must be a string.');
    }
    return value;
  }

  static bool requiredBool(Map<String, dynamic> json, String field) {
    final value = json[field];
    if (value is! bool) {
      throw FormatException('Invalid API contract: $field must be a boolean.');
    }
    return value;
  }

  static int requiredInt(Map<String, dynamic> json, String field) {
    final value = json[field];
    if (value is! int) {
      throw FormatException('Invalid API contract: $field must be an integer.');
    }
    return value;
  }

  static DateTime requiredDate(Map<String, dynamic> json, String field) {
    final value = requiredString(json, field);
    final parsed = DateTime.tryParse(value);
    if (parsed == null) {
      throw FormatException(
        'Invalid API contract: $field must be an ISO-8601 timestamp.',
      );
    }
    return parsed.toUtc();
  }

  static DateTime? optionalDate(Map<String, dynamic> json, String field) {
    final value = optionalString(json, field);
    if (value == null) return null;
    final parsed = DateTime.tryParse(value);
    if (parsed == null) {
      throw FormatException(
        'Invalid API contract: $field must be an ISO-8601 timestamp.',
      );
    }
    return parsed.toUtc();
  }

  static Map<String, dynamic> requiredObject(
    Map<String, dynamic> json,
    String field,
  ) {
    final value = json[field];
    if (value is! Map) {
      throw FormatException('Invalid API contract: $field must be an object.');
    }
    return immutableObject(value, field);
  }

  static Map<String, dynamic>? optionalObject(
    Map<String, dynamic> json,
    String field,
  ) {
    final value = json[field];
    if (value == null) return null;
    if (value is! Map) {
      throw FormatException('Invalid API contract: $field must be an object.');
    }
    return immutableObject(value, field);
  }

  static List<String> optionalStringList(
    Map<String, dynamic> json,
    String field,
  ) {
    final value = json[field];
    if (value == null) return const [];
    if (value is! List || value.any((item) => item is! String)) {
      throw FormatException(
        'Invalid API contract: $field must be a string array.',
      );
    }
    return List<String>.unmodifiable(value.cast<String>());
  }

  static Map<String, dynamic> immutableObject(Object? value, String field) {
    if (value is! Map) {
      throw FormatException('Invalid API contract: $field must be an object.');
    }
    final result = <String, dynamic>{};
    for (final entry in value.entries) {
      if (entry.key is! String) {
        throw FormatException(
          'Invalid API contract: $field must use string keys.',
        );
      }
      result[entry.key as String] = _immutableJson(
        entry.value,
        '$field.${entry.key}',
      );
    }
    return UnmodifiableMapView(result);
  }

  static Object? _immutableJson(Object? value, String field) {
    if (value == null || value is String || value is num || value is bool) {
      return value;
    }
    if (value is Map) return immutableObject(value, field);
    if (value is List) {
      return List<Object?>.unmodifiable(
        value.indexed.map(
          (entry) => _immutableJson(entry.$2, '$field[${entry.$1}]'),
        ),
      );
    }
    throw FormatException(
      'Invalid API contract: $field contains a non-JSON value.',
    );
  }
}
