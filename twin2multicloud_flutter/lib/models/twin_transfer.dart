import 'dart:typed_data';

import 'package:equatable/equatable.dart';

class TwinDuplicateRequest extends Equatable {
  final String name;

  TwinDuplicateRequest({required String name}) : name = _validatedName(name);

  Map<String, dynamic> toJson() => {'name': name};

  @override
  List<Object?> get props => [name];
}

class TwinImportRequest extends Equatable {
  static const maxArchiveBytes = 128 * 1024 * 1024;

  final String newName;
  final String filename;
  final Uint8List _bytes;

  TwinImportRequest({
    required String newName,
    required String filename,
    required Uint8List bytes,
  }) : newName = _validatedName(newName),
       filename = _portableFilename(filename),
       _bytes = _validatedBytes(bytes, maxArchiveBytes, 'archive');

  Uint8List get bytes => Uint8List.fromList(_bytes);

  @override
  List<Object?> get props => [newName, filename];
}

class PortableTwinDownload extends Equatable {
  static const mediaTypeZip = 'application/zip';

  final String filename;
  final String mediaType;
  final Uint8List _bytes;

  PortableTwinDownload({
    required String filename,
    required String mediaType,
    required Uint8List bytes,
  }) : filename = _portableFilename(filename),
       mediaType = _validatedMediaType(mediaType),
       _bytes = _validatedBytes(
         bytes,
         TwinImportRequest.maxArchiveBytes,
         'archive',
       );

  Uint8List get bytes => Uint8List.fromList(_bytes);

  @override
  List<Object?> get props => [filename, mediaType];
}

String _validatedName(String value) {
  final normalized = value.trim();
  if (normalized.isEmpty || normalized.length > 120) {
    throw ArgumentError('Twin name must contain between 1 and 120 characters.');
  }
  return normalized;
}

String _portableFilename(String value) {
  final normalized = value.trim();
  final safe = RegExp(
    r'^[A-Za-z0-9][A-Za-z0-9._-]*\.twin\.zip$',
    caseSensitive: false,
  );
  if (normalized.contains('..') || !safe.hasMatch(normalized)) {
    throw const FormatException(
      'Invalid portable Twin contract: filename must be a safe .twin.zip name.',
    );
  }
  return normalized;
}

String _validatedMediaType(String value) {
  final normalized = value.split(';').first.trim().toLowerCase();
  if (normalized != PortableTwinDownload.mediaTypeZip) {
    throw const FormatException(
      'Invalid portable Twin contract: media type must be application/zip.',
    );
  }
  return PortableTwinDownload.mediaTypeZip;
}

Uint8List _validatedBytes(Uint8List value, int maximum, String label) {
  if (value.isEmpty || value.length > maximum) {
    throw ArgumentError('$label size is outside the supported boundary.');
  }
  return Uint8List.fromList(value);
}
