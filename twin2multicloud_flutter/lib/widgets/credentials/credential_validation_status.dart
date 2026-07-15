// lib/widgets/credentials/credential_validation_status.dart
// Extracted credential validation status display widget

import 'package:flutter/material.dart';

/// Validation state for credentials
enum CredentialValidationState { none, validating, valid, invalid }

/// Displays the validation status of credentials.
///
/// Shows:
/// - Loading indicator when validating
/// - Success checkmark when valid
/// - Error indicator with message when invalid
/// - Optional dual-service status (Optimizer + Deployer)
class CredentialValidationStatus extends StatelessWidget {
  final CredentialValidationState state;
  final String? message;
  final String? optimizerMessage;
  final String? deployerMessage;
  final bool showDualServices;

  const CredentialValidationStatus({
    super.key,
    required this.state,
    this.message,
    this.optimizerMessage,
    this.deployerMessage,
    this.showDualServices = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    switch (state) {
      case CredentialValidationState.none:
        return const SizedBox.shrink();

      case CredentialValidationState.validating:
        return Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: theme.colorScheme.primaryContainer.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            children: [
              SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: theme.colorScheme.primary,
                ),
              ),
              const SizedBox(width: 12),
              Text(
                'Validating credentials...',
                style: TextStyle(
                  color: theme.colorScheme.primary,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        );

      case CredentialValidationState.valid:
        return Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.green.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: Colors.green.withValues(alpha: 0.3)),
          ),
          child: Row(
            children: [
              const Icon(Icons.check_circle, color: Colors.green, size: 20),
              const SizedBox(width: 12),
              Expanded(
                child: showDualServices
                    ? _buildDualServiceStatus(theme, true)
                    : Text(
                        message ?? 'Credentials validated successfully',
                        style: const TextStyle(
                          color: Colors.green,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
              ),
            ],
          ),
        );

      case CredentialValidationState.invalid:
        return Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: theme.colorScheme.errorContainer.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: theme.colorScheme.error.withValues(alpha: 0.3),
            ),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(
                Icons.error_outline,
                color: theme.colorScheme.error,
                size: 20,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: showDualServices
                    ? _buildDualServiceStatus(theme, false)
                    : Text(
                        message ?? 'Validation failed',
                        style: TextStyle(
                          color: theme.colorScheme.error,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
              ),
            ],
          ),
        );
    }
  }

  Widget _buildDualServiceStatus(ThemeData theme, bool overallValid) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          overallValid ? 'Credentials validated' : 'Validation issues',
          style: TextStyle(
            color: overallValid ? Colors.green : theme.colorScheme.error,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 8),
        _buildServiceRow('Optimizer', optimizerMessage, theme),
        const SizedBox(height: 4),
        _buildServiceRow('Deployer', deployerMessage, theme),
      ],
    );
  }

  Widget _buildServiceRow(String service, String? message, ThemeData theme) {
    final isValid =
        message == null ||
        message.toLowerCase().contains('ok') ||
        message.toLowerCase().contains('valid');

    return Row(
      children: [
        Icon(
          isValid ? Icons.check_circle : Icons.warning,
          size: 16,
          color: isValid ? Colors.green : theme.colorScheme.error,
        ),
        const SizedBox(width: 8),
        Text(
          '$service: ${message ?? 'OK'}',
          style: TextStyle(
            fontSize: 13,
            color: isValid ? Colors.green.shade700 : theme.colorScheme.error,
          ),
        ),
      ],
    );
  }
}
