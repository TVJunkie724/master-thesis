import 'dart:io';

Future<void> writeBytesToPath(String path, List<int> bytes) async {
  await File(path).writeAsBytes(bytes);
}

Future<void> writeTextToPath(String path, String content) async {
  await File(path).writeAsString(content);
}
