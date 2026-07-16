import 'package:web/web.dart' as web;

import 'external_auth_launcher.dart';

ExternalAuthLauncher createSystemExternalAuthLauncher() =>
    const _WebExternalAuthLauncher();

class _WebExternalAuthLauncher implements ExternalAuthLauncher {
  const _WebExternalAuthLauncher();

  @override
  ExternalAuthLaunchHandle reserve() {
    final popup = web.window.open('about:blank', '_blank', 'popup');
    popup?.opener = null;
    return _WebExternalAuthLaunchHandle(popup);
  }
}

class _WebExternalAuthLaunchHandle implements ExternalAuthLaunchHandle {
  const _WebExternalAuthLaunchHandle(this.popup);

  final web.Window? popup;

  @override
  Future<bool> navigate(Uri uri) async {
    final target = popup;
    if (target == null || target.closed) return false;
    target.location.href = uri.toString();
    target.focus();
    return true;
  }

  @override
  Future<void> close() async {
    final target = popup;
    if (target != null && !target.closed) target.close();
  }
}
