import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../bloc/wizard/wizard.dart';
import '../../../models/cloud_connection.dart';
import '../../../theme/spacing.dart';
import '../../../widgets/cloud_connections/cloud_connections_group.dart';

class CloudAccessTask extends StatelessWidget {
  const CloudAccessTask({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<WizardBloc, WizardState>(
      builder: (context, state) {
        final bloc = context.read<WizardBloc>();
        final providers = CloudProvider.values
            .where(
              (provider) => state.layerProviders.values.any(
                (required) => required == provider.name.toUpperCase(),
              ),
            )
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
                    'Bind deployment access only for providers used by the selected architecture.',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
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
