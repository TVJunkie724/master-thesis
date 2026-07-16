import 'package:flutter/foundation.dart' show defaultTargetPlatform, kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app.dart';
import 'config/app_runtime.dart';
import 'config/runtime_composition.dart';
import 'config/supported_platforms.dart';
import 'providers/runtime_providers.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final appPlatform = resolveSupportedAppPlatform(
    isWeb: kIsWeb,
    nativePlatform: defaultTargetPlatform,
  );
  if (appPlatform == null) {
    throw UnsupportedError(
      'Twin2MultiCloud supports Web, macOS, Windows, and Linux only. '
      'Run with: flutter run -d chrome | -d macos | -d windows | -d linux',
    );
  }

  final composition = await RuntimeComposition.bootstrap(
    AppRuntimeConfig.fromEnvironment(),
  );

  runApp(
    ProviderScope(
      overrides: [
        appRuntimeProvider.overrideWithValue(composition.config),
        apiServiceProvider.overrideWithValue(composition.managementApi),
        logStreamClientFactoryProvider.overrideWithValue(
          composition.logStreamClientFactory,
        ),
        initialUserProvider.overrideWithValue(composition.initialUser),
      ],
      child: Twin2MultiCloudApp(),
    ),
  );
}
