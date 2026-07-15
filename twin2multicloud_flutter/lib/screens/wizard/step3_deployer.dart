import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../bloc/wizard/wizard.dart';
import '../../features/configuration_workspace/domain/configuration_journey.dart';
import '../../features/configuration_workspace/presentation/deployment/deployment_task_content.dart';
import '../../utils/api_error_handler.dart';
import '../../widgets/file_inputs/zip_upload_block.dart';
import '../../widgets/step3/step3_layout_widgets.dart';

/// Smart boundary for deployment task state and platform file selection.
class Step3Deployer extends StatefulWidget {
  final ConfigurationTaskId? taskId;

  const Step3Deployer({super.key, this.taskId});

  @override
  State<Step3Deployer> createState() => _Step3DeployerState();
}

class _Step3DeployerState extends State<Step3Deployer> {
  String? _selectedZipFileName;

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<WizardBloc, WizardState>(
      builder: (context, state) {
        return Column(
          children: [
            Expanded(
              child: state.calcResult == null
                  ? const Step3NoResultMessage()
                  : DeploymentTaskContent(
                      state: state,
                      taskId: widget.taskId,
                      onEvent: context.read<WizardBloc>().add,
                      zipUploadBlock: ZipUploadBlock(
                        selectedFileName: _selectedZipFileName,
                        isUploading: state.zipUploadInProgress,
                        hasError: state.errorMessage != null,
                        onSelect: _pickAndUploadZip,
                        onClear: () {
                          setState(() => _selectedZipFileName = null);
                        },
                      ),
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

  Future<void> _pickAndUploadZip() async {
    try {
      final result = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['zip'],
        withData: true,
      );
      if (result == null || result.files.isEmpty || !mounted) return;

      final file = result.files.single;
      final bytes = file.bytes;
      if (bytes == null) {
        _showFileError('Failed to read file');
        return;
      }

      final bloc = context.read<WizardBloc>();
      if (bloc.state.hasSection3Data) {
        final confirmed = await _confirmZipReplacement();
        if (confirmed != true || !mounted) return;
      }

      setState(() => _selectedZipFileName = file.name);
      bloc.add(WizardZipUploadRequested(fileBytes: bytes, fileName: file.name));
    } catch (error) {
      if (!mounted) return;
      _showFileError(
        'Failed to select file: ${ApiErrorHandler.extractMessage(error)}',
      );
    }
  }

  Future<bool?> _confirmZipReplacement() {
    return showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        icon: Icon(
          Icons.warning_amber,
          size: 48,
          color: Colors.orange.shade700,
        ),
        title: const Text('Replace Existing Data?'),
        content: const Text(
          'Uploading this zip will replace your current deployment artifacts.\n\n'
          'This includes events, devices, payloads, processors, and other fields '
          'you have already entered.\n\n'
          'This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(dialogContext, true),
            style: FilledButton.styleFrom(
              backgroundColor: Colors.orange.shade700,
            ),
            child: const Text('Replace'),
          ),
        ],
      ),
    );
  }

  void _showFileError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red.shade700),
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

      if (result == null || result.files.isEmpty || !mounted) return;
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
      if (!mounted) return;
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
