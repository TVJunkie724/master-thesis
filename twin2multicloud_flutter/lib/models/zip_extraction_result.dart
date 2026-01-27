/// Models for ZIP extraction API response.
/// Used by the wizard to auto-populate Step 3 fields from uploaded project.zip.
library;

/// Result of extracting a single file from the ZIP.
class FileExtractionResult {
  final bool exists;
  final String? content; // UTF-8 for text, base64 for binary
  final bool isBinary;
  final String? validationError;
  final bool? saved; // For GLB: true if saved to server

  FileExtractionResult({
    required this.exists,
    this.content,
    this.isBinary = false,
    this.validationError,
    this.saved,
  });

  factory FileExtractionResult.fromJson(Map<String, dynamic> json) {
    return FileExtractionResult(
      exists: json['exists'] ?? false,
      content: json['content'],
      isBinary: json['is_binary'] ?? false,
      validationError: json['validation_error'],
      saved: json['saved'],
    );
  }
}

/// Extracted function code from processor/action/feedback directories.
class FunctionExtractionResult {
  final Map<String, FileExtractionResult> processors; // keyed by device ID
  final Map<String, FileExtractionResult> eventActions; // keyed by action name
  final FileExtractionResult? eventFeedback;

  FunctionExtractionResult({
    this.processors = const {},
    this.eventActions = const {},
    this.eventFeedback,
  });

  factory FunctionExtractionResult.fromJson(Map<String, dynamic> json) {
    return FunctionExtractionResult(
      processors:
          (json['processors'] as Map<String, dynamic>?)?.map(
            (k, v) => MapEntry(k, FileExtractionResult.fromJson(v)),
          ) ??
          {},
      eventActions:
          (json['event_actions'] as Map<String, dynamic>?)?.map(
            (k, v) => MapEntry(k, FileExtractionResult.fromJson(v)),
          ) ??
          {},
      eventFeedback: json['event_feedback'] != null
          ? FileExtractionResult.fromJson(json['event_feedback'])
          : null,
    );
  }
}

/// Extracted binary assets (GLB files for 3D visualization).
class AssetExtractionResult {
  final FileExtractionResult? sceneGlb;

  AssetExtractionResult({this.sceneGlb});

  factory AssetExtractionResult.fromJson(Map<String, dynamic> json) {
    return AssetExtractionResult(
      sceneGlb: json['scene_glb'] != null
          ? FileExtractionResult.fromJson(json['scene_glb'])
          : null,
    );
  }
}

/// Full response from /twins/{id}/deployer/upload-zip endpoint.
class ZipExtractionResult {
  final bool success;
  final Map<String, FileExtractionResult> files; // config files by name
  final FunctionExtractionResult functions;
  final AssetExtractionResult assets;
  final List<String> validationErrors;
  final List<String> warnings;

  ZipExtractionResult({
    required this.success,
    this.files = const {},
    FunctionExtractionResult? functions,
    AssetExtractionResult? assets,
    this.validationErrors = const [],
    this.warnings = const [],
  }) : functions = functions ?? FunctionExtractionResult(),
       assets = assets ?? AssetExtractionResult();

  factory ZipExtractionResult.fromJson(Map<String, dynamic> json) {
    return ZipExtractionResult(
      success: json['success'] ?? false,
      files:
          (json['files'] as Map<String, dynamic>?)?.map(
            (k, v) => MapEntry(k, FileExtractionResult.fromJson(v)),
          ) ??
          {},
      functions: json['functions'] != null
          ? FunctionExtractionResult.fromJson(json['functions'])
          : FunctionExtractionResult(),
      assets: json['assets'] != null
          ? AssetExtractionResult.fromJson(json['assets'])
          : AssetExtractionResult(),
      validationErrors: List<String>.from(json['validation_errors'] ?? []),
      warnings: List<String>.from(json['warnings'] ?? []),
    );
  }

  /// Check if any config file content was extracted
  bool get hasConfigContent =>
      files.values.any((f) => f.exists && f.content != null);

  /// Check if any processor code was extracted
  bool get hasProcessorContent =>
      functions.processors.values.any((f) => f.exists && f.content != null);
}
