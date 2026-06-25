import 'package:equatable/equatable.dart';

class ValidationResult extends Equatable {
  final bool valid;
  final String message;

  const ValidationResult({required this.valid, required this.message});

  factory ValidationResult.fromJson(
    Map<String, dynamic> json, {
    String validMessage = 'Valid',
    String invalidMessage = 'Validation failed',
  }) {
    final valid = json['valid'] == true;
    return ValidationResult(
      valid: valid,
      message:
          json['message']?.toString() ??
          (valid ? validMessage : invalidMessage),
    );
  }

  Map<String, dynamic> toJson() => {'valid': valid, 'message': message};

  @override
  List<Object?> get props => [valid, message];
}
