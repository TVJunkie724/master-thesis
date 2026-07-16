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
  Future<void> close() async {}
}
