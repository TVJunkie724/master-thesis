import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

/// Shared native file-selection control.
///
/// Feature widgets provide accepted extensions and translate the selected
/// platform file into their typed domain command.
class PlatformFileSelectionButton extends StatelessWidget {
  final List<String> allowedExtensions;
  final String label;
  final IconData icon;
  final bool withData;
  final ValueChanged<PlatformFile> onSelected;

  const PlatformFileSelectionButton({
    super.key,
    required this.allowedExtensions,
    required this.label,
    required this.icon,
    required this.onSelected,
    this.withData = false,
  });

  Future<void> _select() async {
    final result = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: allowedExtensions,
      withData: withData,
    );
    if (result == null || result.files.length != 1) return;
    onSelected(result.files.single);
  }

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: _select,
      icon: Icon(icon),
      label: Text(label),
    );
  }
}
