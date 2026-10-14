import 'dart:async';
import 'dart:js_interop';

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
  Future<bool> renderHtml(String html) async {
    final blob = web.Blob(
      [html.toJS].toJS,
      web.BlobPropertyBag(type: 'text/html'),
    );
    final url = web.URL.createObjectURL(blob);
    try {
      return await navigate(Uri.parse(url));
    } finally {
      Timer(const Duration(minutes: 1), () => web.URL.revokeObjectURL(url));
    }
  }

  @override
  Future<void> close() async {
    final target = popup;
    if (target != null && !target.closed) target.close();
  }
}
