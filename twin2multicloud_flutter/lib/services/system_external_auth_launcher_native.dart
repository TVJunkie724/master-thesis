import 'dart:async';
import 'dart:io';

import 'package:url_launcher/url_launcher.dart';

import 'external_auth_launcher.dart';

ExternalAuthLauncher createSystemExternalAuthLauncher() =>
    const _NativeExternalAuthLauncher();

class _NativeExternalAuthLauncher implements ExternalAuthLauncher {
  const _NativeExternalAuthLauncher();

  @override
  ExternalAuthLaunchHandle reserve() => const _NativeExternalAuthLaunchHandle();
}

class _NativeExternalAuthLaunchHandle implements ExternalAuthLaunchHandle {
  const _NativeExternalAuthLaunchHandle();

  @override
  Future<bool> navigate(Uri uri) =>
      launchUrl(uri, mode: LaunchMode.externalApplication);

  @override
  Future<bool> renderHtml(String html) async {
    final directory = await Directory.systemTemp.createTemp('t2mc-l5-');
    try {
      final file = await File(
        '${directory.path}/view.html',
      ).writeAsString(html);
      return await navigate(file.uri);
    } finally {
      Timer(const Duration(minutes: 1), () async {
        try {
          await directory.delete(recursive: true);
        } on FileSystemException {
          // The OS may already have reclaimed its temporary directory.
        }
      });
    }
  }

  @override
  Future<void> close() async {}
}
