import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../bloc/wizard/wizard.dart';
import '../../../models/cloud_connection.dart';
import '../../../theme/spacing.dart';
import '../../../widgets/cloud_connections/cloud_connections_group.dart';

class CloudAccessTask extends ConsumerWidget {
  const CloudAccessTask({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return BlocBuilder<WizardBloc, WizardState>(
      builder: (context, state) {
        final bloc = context.read<WizardBloc>();
        final providers = CloudProvider.values
            .where(state.requiredDeploymentProviders.contains)
            .toList(growable: false);

        return SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: AppSpacing.maxContentWidthMedium,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Cloud access',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    'Select a preconfigured PoC credential for every provider used by the selected architecture.',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(AppSpacing.md),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            'Required by the selected architecture',
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          const SizedBox(height: AppSpacing.sm),
                          for (final provider in providers)
                            ListTile(
                              contentPadding: EdgeInsets.zero,
                              leading: const Icon(Icons.cloud_outlined),
                              title: Text(provider.label),
                              subtitle: Text(
                                state.selectedCloudConnectionIds[provider] ==
                                        null
                                    ? 'Preconfigured deployment access is missing.'
                                    : 'Preconfigured deployment access selected.',
                              ),
                              trailing:
                                  state.selectedCloudConnectionIds[provider] ==
                                      null
                                  ? const Icon(Icons.key_outlined)
                                  : const Icon(Icons.check_circle_outline),
                            ),
                          const SizedBox(height: AppSpacing.sm),
                          Text(
                            'For this PoC, an existing non-root administrator credential is entered manually. Provider prerequisites are checked later by deployment preflight.',
                            style: Theme.of(context).textTheme.bodySmall,
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  CloudConnectionsGroup(
                    providers: providers,
                    connectionsByProvider: state.cloudConnections,
                    selectedConnectionIds: state.selectedCloudConnectionIds,
                    loadingByProvider: state.cloudConnectionLoading,
                    errorByProvider: state.cloudConnectionErrors,
                    validationByProvider: state.cloudConnectionValidation,
                    onSelected: (provider, connectionId) => bloc.add(
                      WizardCloudConnectionSelected(provider, connectionId),
                    ),
                    onCreate: (provider, request) => bloc.add(
                      WizardCloudConnectionCreateRequested(provider, request),
                    ),
                    onValidate: (provider, connectionId) => bloc.add(
                      WizardCloudConnectionValidateRequested(
                        provider,
                        connectionId,
                      ),
                    ),
                    onUnbind: (provider) =>
                        bloc.add(WizardCloudConnectionUnbound(provider)),
                    onDelete: (provider, connectionId) => bloc.add(
                      WizardCloudConnectionDeleteRequested(
                        provider,
                        connectionId,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}
