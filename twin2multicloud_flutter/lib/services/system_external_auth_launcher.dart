import 'external_auth_launcher.dart';
import 'system_external_auth_launcher_native.dart'
    if (dart.library.js_interop) 'system_external_auth_launcher_web.dart'
    as platform;

ExternalAuthLauncher createSystemExternalAuthLauncher() =>
    platform.createSystemExternalAuthLauncher();
