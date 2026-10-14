import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../bloc/wizard/wizard.dart';
import '../../features/configuration_workspace/domain/configuration_journey.dart';
import '../../features/configuration_workspace/presentation/deployment/deployment_task_content.dart';
import '../../utils/api_error_handler.dart';
import '../../widgets/step3/step3_layout_widgets.dart';

/// Smart boundary for deployment task state and platform file selection.
class Step3Deployer extends StatelessWidget {
  final ConfigurationTaskId? taskId;

  const Step3Deployer({super.key, this.taskId});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<WizardBloc, WizardState>(
      builder: (context, state) {
        final requiresOptimizationResult =
            taskId != ConfigurationTaskId.userLogic;
        return Column(
          children: [
            Expanded(
              child: state.calcResult == null && requiresOptimizationResult
                  ? const Step3NoResultMessage()
                  : DeploymentTaskContent(
                      state: state,
                      taskId: taskId,
                      onEvent: context.read<WizardBloc>().add,
                      onUploadGlb: () => _pickAndUploadSceneGlb(context),
                      onDeleteGlb: () {
                        context.read<WizardBloc>().add(
                          const WizardSceneGlbDeleteRequested(),
                        );
                      },
                    ),
            ),
          ],
        );
      },
    );
  }

  Future<void> _pickAndUploadSceneGlb(BuildContext context) async {
    final bloc = context.read<WizardBloc>();
    final messenger = ScaffoldMessenger.of(context);
    try {
      final result = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['glb'],
        withData: true,
      );

      if (result == null || result.files.isEmpty || !context.mounted) return;
      final file = result.files.first;
      final bytes = file.bytes;
      if (bytes == null) {
        messenger.showSnackBar(
          const SnackBar(content: Text('Failed to read file')),
        );
        return;
      }

      bloc.add(
        WizardSceneGlbUploadRequested(bytes: bytes, filename: file.name),
      );
    } catch (error) {
      if (!context.mounted) return;
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            'Failed to select file: ${ApiErrorHandler.extractMessage(error)}',
          ),
        ),
      );
    }
  }
}
