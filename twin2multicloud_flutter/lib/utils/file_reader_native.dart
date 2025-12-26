import 'dart:io';
import 'package:file_picker/file_picker.dart';

/// Read a picked file on native platforms (Windows, macOS, Linux, iOS, Android)
Future<String> readPickedFile(PlatformFile file) async {
  if (file.path != null) {
    return await File(file.path!).readAsString();
  }
  if (file.bytes != null) {
    return String.fromCharCodes(file.bytes!);
  }
  throw Exception('Unable to read file');
}
