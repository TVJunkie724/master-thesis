import 'package:flutter/material.dart';
import 'result.dart';

/// Centralized error display utilities.
/// 
/// Provides consistent error presentation across the application.
class ErrorHandler {
  /// Shows an error message in a floating snackbar.
  static void showError(BuildContext context, AppException error) {
    if (!context.mounted) return;
    
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.error_outline, color: Colors.white),
            const SizedBox(width: 8),
            Expanded(child: Text(error.message)),
          ],
        ),
        backgroundColor: Colors.red.shade700,
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.all(16),
        duration: const Duration(seconds: 4),
      ),
    );
  }
  
  /// Shows a simple error message (without AppException).
  static void showErrorMessage(BuildContext context, String message) {
    showError(context, AppException(message));
  }
  
  /// Shows a success message in a floating snackbar.
  static void showSuccess(BuildContext context, String message) {
    if (!context.mounted) return;
    
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(
          children: [
            const Icon(Icons.check_circle_outline, color: Colors.white),
            const SizedBox(width: 8),
            Expanded(child: Text(message)),
          ],
        ),
        backgroundColor: Colors.green.shade700,
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.all(16),
        duration: const Duration(seconds: 3),
      ),
    );
  }
}
