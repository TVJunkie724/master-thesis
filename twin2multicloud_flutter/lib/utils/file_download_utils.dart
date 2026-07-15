/// File download utilities for cross-platform file persistence.
///
/// Web: uses file_saver (browser download).
/// Desktop: uses file_picker save dialog + dart:io to write bytes.
library;

import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:file_saver/file_saver.dart';
import 'package:flutter/foundation.dart';

/// Result of a file save operation.
class FileSaveResult {
  final bool success;
  final bool cancelled;
  final String? message;
  final String? error;

  FileSaveResult({
    this.success = false,
    this.cancelled = false,
    this.message,
    this.error,
  });
}

/// Save binary data to a file using a native save dialog.
///
/// Returns [FileSaveResult] with success/cancelled/error status.
Future<FileSaveResult> saveBinaryFile({
  required Uint8List bytes,
  required String suggestedName,
  String? mimeType,
}) async {
  try {
    final dotIndex = suggestedName.lastIndexOf('.');
    final hasExtension = dotIndex > 0 && dotIndex < suggestedName.length - 1;
    final baseName = hasExtension
        ? suggestedName.substring(0, dotIndex)
        : suggestedName;
    final extension = hasExtension
        ? suggestedName.substring(dotIndex + 1)
        : 'bin';

    if (kIsWeb) {
      // Web: trigger a browser download via file_saver
      await FileSaver.instance.saveFile(
        name: baseName,
        bytes: bytes,
        fileExtension: extension,
        mimeType: MimeType.custom,
        customMimeType: mimeType ?? 'application/octet-stream',
      );
      return FileSaveResult(
        success: true,
        message: 'Downloaded $suggestedName',
      );
    }

    // Desktop: native Save-As dialog, then write bytes ourselves
    final outputPath = await FilePicker.saveFile(
      dialogTitle: 'Save $suggestedName',
      fileName: suggestedName,
      type: FileType.custom,
      allowedExtensions: [extension],
    );

    if (outputPath == null) {
      return FileSaveResult(cancelled: true);
    }

    await File(outputPath).writeAsBytes(bytes);
    return FileSaveResult(success: true, message: 'Saved to $outputPath');
  } catch (e) {
    return FileSaveResult(error: 'Save failed: $e');
  }
}
