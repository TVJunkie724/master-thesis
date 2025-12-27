import 'dart:convert';
import 'package:file_picker/file_picker.dart';

/// Read a picked file on web platform
Future<String> readPickedFile(PlatformFile file) async {
  if (file.bytes != null) {
    return utf8.decode(file.bytes!);
  }
  throw Exception('Unable to read file on web');
}
