import 'package:flutter/material.dart';

import '../../models/cloud_connection.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import 'cloud_connection_strings.dart';

class CloudConnectionValidationStatus extends StatelessWidget {
  final CloudConnection? connection;
  final CloudConnectionValidationResult? validation;
  final bool isLoading;

  const CloudConnectionValidationStatus({
    super.key,
    required this.connection,
    required this.validation,
    required this.isLoading,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final status =
        validation?.validationStatus ??
        connection?.validationStatus ??
        CloudConnectionStrings.notValidated;
    final message = validation?.message ?? connection?.validationMessage;
    final valid = validation?.valid ?? connection?.isValid ?? false;
    final color = isLoading
        ? theme.colorScheme.primary
        : valid
        ? AppColors.success
        : status == 'invalid'
        ? theme.colorScheme.error
        : theme.colorScheme.onSurfaceVariant;
    final icon = isLoading
        ? Icons.sync
        : valid
        ? Icons.check_circle
        : status == 'invalid'
        ? Icons.error_outline
        : Icons.info_outline;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: color),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                isLoading ? 'Validating...' : _formatStatus(status),
                style: theme.textTheme.bodyMedium?.copyWith(color: color),
              ),
              if (message != null && message.isNotEmpty)
                Text(
                  message,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }

  String _formatStatus(String value) {
    return switch (value) {
      'valid' => 'Valid',
      'invalid' => 'Invalid',
      'untested' => CloudConnectionStrings.notValidated,
      _ => value,
    };
  }
}
