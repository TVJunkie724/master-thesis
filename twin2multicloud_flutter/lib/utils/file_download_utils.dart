/// File download utilities for cross-platform file persistence.
///
/// Uses file_selector to trigger native "Save As" dialog on all platforms.

import 'dart:typed_data';
import 'package:file_selector/file_selector.dart';

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

/// Save binary data to a file using native save dialog.
///
/// Returns [FileSaveResult] with success/cancelled/error status.
Future<FileSaveResult> saveBinaryFile({
  required Uint8List bytes,
  required String suggestedName,
  String? mimeType,
}) async {
  try {
    // Trigger native "Save As" dialog
    final FileSaveLocation? location = await getSaveLocation(
      suggestedName: suggestedName,
    );

    if (location == null) {
      return FileSaveResult(cancelled: true);
    }

    // Create XFile from bytes and save
    final XFile file = XFile.fromData(
      bytes,
      mimeType: mimeType ?? 'application/zip',
    );
    await file.saveTo(location.path);

    return FileSaveResult(success: true, message: 'Saved to ${location.path}');
  } catch (e) {
    return FileSaveResult(error: 'Save failed: $e');
  }
}
