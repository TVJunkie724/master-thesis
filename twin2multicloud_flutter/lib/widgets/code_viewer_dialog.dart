// lib/widgets/code_viewer_dialog.dart
// Reusable syntax-highlighted code viewer dialog with copy functionality
// Cross-platform download: file_picker save dialog for desktop, file_saver for web

import 'dart:convert';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_code_editor/flutter_code_editor.dart';
import 'package:flutter_highlight/themes/monokai-sublime.dart';
import 'package:highlight/highlight_core.dart' show Mode;
import 'package:highlight/languages/json.dart' as hl_json;
import 'package:highlight/languages/python.dart' as hl_python;
import 'package:highlight/languages/yaml.dart' as hl_yaml;
import 'package:file_picker/file_picker.dart';
import 'package:file_saver/file_saver.dart';

import '../utils/file_writer.dart';

/// Result of a download operation
class DownloadResult {
  final bool success;
  final bool cancelled;
  final String? message;
  final String? error;

  const DownloadResult({
    required this.success,
    this.cancelled = false,
    this.message,
    this.error,
  });
}

/// Show a dialog with syntax-highlighted code and copy option.
void showCodeViewerDialog(
  BuildContext context, {
  required String title,
  required String code,
  String? filename,
}) {
  showDialog(
    context: context,
    builder: (ctx) =>
        _CodeViewerDialog(title: title, code: code, filename: filename),
  );
}

/// Get file extension from filename
String _getFileExtension(String filename) {
  final lower = filename.toLowerCase();
  if (lower.endsWith('.json') ||
      lower.contains('json') ||
      lower.contains('pricing')) {
    return '.json';
  } else if (lower.endsWith('.py') ||
      lower.contains('python') ||
      lower.contains('lambda') ||
      lower.contains('function')) {
    return '.py';
  } else if (lower.endsWith('.yaml') ||
      lower.endsWith('.yml') ||
      lower.contains('workflow')) {
    return '.yaml';
  }
  return '.txt';
}

/// Get MIME type for extension
MimeType _getMimeType(String extension) {
  switch (extension) {
    case '.json':
      return MimeType.json;
    case '.py':
      return MimeType.text;
    case '.yaml':
      return MimeType.text;
    default:
      return MimeType.text;
  }
}

/// Clean up filename for saving
String _cleanFilename(String filename, String extension) {
  String clean = filename
      .replaceAll('/', '_')
      .replaceAll(' ', '_')
      .replaceAll(RegExp(r'[^a-zA-Z0-9_.-]'), '');

  if (!clean.endsWith(extension)) {
    // Remove any existing extension and add correct one
    final dotIndex = clean.lastIndexOf('.');
    if (dotIndex > 0) {
      clean = clean.substring(0, dotIndex);
    }
    clean += extension;
  }
  return clean;
}

/// Download content as a file.
/// - Web: Uses file_saver (browser download)
/// - Desktop (macOS/Windows/Linux): Uses file_picker save dialog
/// Returns a DownloadResult - caller is responsible for showing messages.
Future<DownloadResult> downloadCodeFile({
  required String content,
  required String filename,
}) async {
  try {
    final extension = _getFileExtension(filename);
    final cleanName = _cleanFilename(filename, extension);
    final bytes = utf8.encode(content);

    if (kIsWeb) {
      // Web: Use file_saver - creates browser download
      await FileSaver.instance.saveFile(
        name: cleanName.replaceAll(extension, ''),
        bytes: Uint8List.fromList(bytes),
        fileExtension: extension.substring(1), // Remove leading dot
        mimeType: _getMimeType(extension),
      );

      return DownloadResult(success: true, message: 'Downloaded $cleanName');
    } else {
      // Desktop: Use file_picker save dialog
      final outputPath = await FilePicker.saveFile(
        dialogTitle: 'Save $cleanName',
        fileName: cleanName,
        type: FileType.custom,
        allowedExtensions: [extension.substring(1)], // Remove leading dot
      );

      if (outputPath == null) {
        // User cancelled
        return const DownloadResult(success: false, cancelled: true);
      }

      await writeTextToPath(outputPath, content);

      return DownloadResult(success: true, message: 'Saved to $outputPath');
    }
  } catch (e) {
    return DownloadResult(success: false, error: 'Download failed: $e');
  }
}

class _CodeViewerDialog extends StatefulWidget {
  final String title;
  final String code;
  final String? filename;

  const _CodeViewerDialog({
    required this.title,
    required this.code,
    this.filename,
  });

  @override
  State<_CodeViewerDialog> createState() => _CodeViewerDialogState();
}

class _CodeViewerDialogState extends State<_CodeViewerDialog> {
  late CodeController _controller;

  @override
  void initState() {
    super.initState();
    _controller = CodeController(
      text: widget.code,
      language: _getLanguage(widget.filename ?? widget.title),
      readOnly: true,
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Mode? _getLanguage(String filename) {
    final lower = filename.toLowerCase();
    if (lower.endsWith('.json') || lower.contains('json')) {
      return hl_json.json;
    }
    if (lower.endsWith('.py') ||
        lower.contains('python') ||
        lower.contains('lambda')) {
      return hl_python.python;
    }
    if (lower.endsWith('.yaml') || lower.endsWith('.yml')) {
      return hl_yaml.yaml;
    }
    return hl_json.json; // Default to JSON
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Row(
        children: [
          Expanded(child: Text(widget.title)),
          IconButton(
            icon: const Icon(Icons.copy),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: widget.code));
              // Note: Caller should handle messaging through BLoC
              Navigator.of(context).pop('copied');
            },
            tooltip: 'Copy to clipboard',
          ),
        ],
      ),
      content: Container(
        width: 700,
        height: 500,
        decoration: BoxDecoration(
          color: const Color(0xFF2A2A2A),
          borderRadius: BorderRadius.circular(8),
        ),
        clipBehavior: Clip.antiAlias,
        child: SingleChildScrollView(
          child: CodeTheme(
            data: CodeThemeData(styles: monokaiSublimeTheme),
            child: CodeField(
              controller: _controller,
              minLines: 1,
              maxLines: null,
              wrap: true,
              gutterStyle: const GutterStyle(
                showLineNumbers: true,
                showErrors: false,
                showFoldingHandles: false,
              ),
              textStyle: const TextStyle(fontFamily: 'monospace', fontSize: 13),
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );
  }
}
