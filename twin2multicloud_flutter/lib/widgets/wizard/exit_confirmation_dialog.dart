// lib/widgets/wizard/exit_confirmation_dialog.dart
// Extracted exit confirmation dialog from wizard_screen.dart

import 'package:flutter/material.dart';

/// A confirmation dialog for exiting the wizard with unsaved changes.
/// 
/// Features:
/// - Save draft option
/// - Discard option
/// - Cancel option
/// - Consistent styling
class ExitConfirmationDialog extends StatelessWidget {
  final bool hasUnsavedChanges;
  final VoidCallback onSaveAndExit;
  final VoidCallback onDiscardAndExit;
  
  const ExitConfirmationDialog({
    super.key,
    required this.hasUnsavedChanges,
    required this.onSaveAndExit,
    required this.onDiscardAndExit,
  });
  
  /// Show the dialog and return the user's choice
  static Future<ExitChoice?> show(
    BuildContext context, {
    required bool hasUnsavedChanges,
  }) async {
    return showDialog<ExitChoice>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.warning_amber_rounded, color: Colors.orange),
            SizedBox(width: 12),
            Text('Exit Wizard?'),
          ],
        ),
        content: Text(
          hasUnsavedChanges
              ? 'You have unsaved changes. What would you like to do?'
              : 'Are you sure you want to exit the wizard?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(null),
            child: const Text('Cancel'),
          ),
          if (hasUnsavedChanges) ...[
            TextButton(
              onPressed: () => Navigator.of(context).pop(ExitChoice.discard),
              style: TextButton.styleFrom(
                foregroundColor: Colors.red,
              ),
              child: const Text('Discard'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(context).pop(ExitChoice.save),
              child: const Text('Save & Exit'),
            ),
          ] else
            FilledButton(
              onPressed: () => Navigator.of(context).pop(ExitChoice.discard),
              child: const Text('Exit'),
            ),
        ],
      ),
    );
  }
  
  @override
  Widget build(BuildContext context) {
    // This widget builds a standalone version if needed
    return AlertDialog(
      title: const Row(
        children: [
          Icon(Icons.warning_amber_rounded, color: Colors.orange),
          SizedBox(width: 12),
          Text('Exit Wizard?'),
        ],
      ),
      content: Text(
        hasUnsavedChanges
            ? 'You have unsaved changes. What would you like to do?'
            : 'Are you sure you want to exit the wizard?',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        if (hasUnsavedChanges) ...[
          TextButton(
            onPressed: onDiscardAndExit,
            style: TextButton.styleFrom(
              foregroundColor: Colors.red,
            ),
            child: const Text('Discard'),
          ),
          FilledButton(
            onPressed: onSaveAndExit,
            child: const Text('Save & Exit'),
          ),
        ] else
          FilledButton(
            onPressed: onDiscardAndExit,
            child: const Text('Exit'),
          ),
      ],
    );
  }
}

/// User's choice when exiting the wizard
enum ExitChoice {
  save,
  discard,
}
