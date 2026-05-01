import 'package:flutter/material.dart';

import '../../models/cloud_connection.dart';
import '../../theme/spacing.dart';
import 'cloud_connection_create_dialog.dart';
import 'cloud_connection_section.dart';
import 'cloud_connection_strings.dart';
import 'legacy_credential_fallback_banner.dart';

class CloudConnectionsGroup extends StatelessWidget {
  final Map<CloudProvider, List<CloudConnection>> connectionsByProvider;
  final Map<CloudProvider, String?> selectedConnectionIds;
  final Map<CloudProvider, bool> loadingByProvider;
  final Map<CloudProvider, String?> errorByProvider;
  final Map<CloudProvider, CloudConnectionValidationResult?>
  validationByProvider;
  final Set<CloudProvider> legacyConfiguredProviders;
  final void Function(CloudProvider provider, String? connectionId) onSelected;
  final void Function(
    CloudProvider provider,
    CloudConnectionCreateRequest request,
  )
  onCreate;
  final void Function(CloudProvider provider, String connectionId) onValidate;
  final void Function(CloudProvider provider) onUnbind;
  final void Function(CloudProvider provider, String connectionId) onDelete;

  const CloudConnectionsGroup({
    super.key,
    required this.connectionsByProvider,
    required this.selectedConnectionIds,
    required this.loadingByProvider,
    required this.errorByProvider,
    required this.validationByProvider,
    required this.legacyConfiguredProviders,
    required this.onSelected,
    required this.onCreate,
    required this.onValidate,
    required this.onUnbind,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          CloudConnectionStrings.title,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: AppSpacing.md),
        for (final provider in CloudProvider.values) ...[
          CloudConnectionSection(
            provider: provider,
            icon: _iconForProvider(provider),
            connections: connectionsByProvider[provider] ?? const [],
            selectedConnectionId: selectedConnectionIds[provider],
            isLoading: loadingByProvider[provider] ?? false,
            errorMessage: errorByProvider[provider],
            validation: validationByProvider[provider],
            onCreate: () => _showCreateDialog(context, provider),
            onValidate: selectedConnectionIds[provider] == null
                ? null
                : () => onValidate(provider, selectedConnectionIds[provider]!),
            onUnbind: () => onUnbind(provider),
            onSelected: (connectionId) => onSelected(provider, connectionId),
            onDelete: (connectionId) => onDelete(provider, connectionId),
          ),
          const SizedBox(height: AppSpacing.md),
        ],
        LegacyCredentialFallbackBanner(providers: legacyConfiguredProviders),
      ],
    );
  }

  Future<void> _showCreateDialog(
    BuildContext context,
    CloudProvider provider,
  ) async {
    final request = await showDialog<CloudConnectionCreateRequest>(
      context: context,
      builder: (context) => CloudConnectionCreateDialog(provider: provider),
    );
    if (request != null && context.mounted) {
      onCreate(provider, request);
    }
  }

  IconData _iconForProvider(CloudProvider provider) {
    return switch (provider) {
      CloudProvider.aws => Icons.cloud,
      CloudProvider.azure => Icons.cloud_circle,
      CloudProvider.gcp => Icons.cloud_queue,
    };
  }
}
