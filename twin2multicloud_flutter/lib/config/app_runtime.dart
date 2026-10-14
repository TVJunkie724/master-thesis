enum AppMode { development, production, demo }

enum DemoScenario { showcase, empty, degraded }

class AppRuntimeConfig {
  final AppMode mode;
  final DemoScenario demoScenario;
  final Uri? managementApiBaseUri;
  final String? _pocAuthToken;

  const AppRuntimeConfig._({
    required this.mode,
    required this.demoScenario,
    required this.managementApiBaseUri,
    required String? pocAuthToken,
  }) : _pocAuthToken = pocAuthToken;

  factory AppRuntimeConfig.development({
    required Uri managementApiBaseUri,
    required String pocAuthToken,
  }) {
    return AppRuntimeConfig._(
      mode: AppMode.development,
      demoScenario: DemoScenario.showcase,
      managementApiBaseUri: _validateBaseUri(
        managementApiBaseUri,
        requireHttps: false,
      ),
      pocAuthToken: _validatePocToken(pocAuthToken),
    );
  }

  factory AppRuntimeConfig.production({
    required Uri managementApiBaseUri,
    required String pocAuthToken,
  }) {
    return AppRuntimeConfig._(
      mode: AppMode.production,
      demoScenario: DemoScenario.showcase,
      managementApiBaseUri: _validateBaseUri(
        managementApiBaseUri,
        requireHttps: true,
      ),
      pocAuthToken: _validatePocToken(pocAuthToken),
    );
  }

  const AppRuntimeConfig.demo({this.demoScenario = DemoScenario.showcase})
    : mode = AppMode.demo,
      managementApiBaseUri = null,
      _pocAuthToken = null;

  factory AppRuntimeConfig.fromEnvironment() {
    const modeValue = String.fromEnvironment('APP_MODE');
    const apiBaseUrl = String.fromEnvironment('API_BASE_URL');
    const pocAuthToken = String.fromEnvironment('POC_AUTH_TOKEN');
    const scenarioValue = String.fromEnvironment(
      'DEMO_SCENARIO',
      defaultValue: 'showcase',
    );

    return AppRuntimeConfig.fromValues(
      appMode: modeValue,
      apiBaseUrl: apiBaseUrl,
      pocAuthToken: pocAuthToken,
      demoScenario: scenarioValue,
    );
  }

  factory AppRuntimeConfig.fromValues({
    required String appMode,
    String apiBaseUrl = '',
    String pocAuthToken = '',
    String demoScenario = 'showcase',
  }) {
    final mode = parseMode(appMode);
    return switch (mode) {
      AppMode.development => AppRuntimeConfig.development(
        managementApiBaseUri: _parseBaseUri(apiBaseUrl),
        pocAuthToken: pocAuthToken,
      ),
      AppMode.production => AppRuntimeConfig.production(
        managementApiBaseUri: _parseBaseUri(apiBaseUrl),
        pocAuthToken: pocAuthToken,
      ),
      AppMode.demo => _demoFromValues(
        apiBaseUrl: apiBaseUrl,
        pocAuthToken: pocAuthToken,
        scenario: demoScenario,
      ),
    };
  }

  bool get isDemo => mode == AppMode.demo;

  String? get initialAuthToken => _pocAuthToken;

  static AppMode parseMode(String value) {
    final normalized = value.trim().toLowerCase();
    if (normalized.isEmpty) {
      throw StateError(
        'APP_MODE is required. Expected development, production, or demo.',
      );
    }
    return switch (normalized) {
      'development' || 'dev' => AppMode.development,
      'production' || 'prod' => AppMode.production,
      'demo' => AppMode.demo,
      _ => throw StateError(
        'Unsupported APP_MODE. Expected development, production, or demo.',
      ),
    };
  }

  static DemoScenario parseScenario(String value) {
    return switch (value.trim().toLowerCase()) {
      'showcase' => DemoScenario.showcase,
      'empty' => DemoScenario.empty,
      'degraded' => DemoScenario.degraded,
      _ => throw StateError(
        'Unsupported DEMO_SCENARIO. Expected showcase, empty, or degraded.',
      ),
    };
  }

  static AppRuntimeConfig _demoFromValues({
    required String apiBaseUrl,
    required String pocAuthToken,
    required String scenario,
  }) {
    if (apiBaseUrl.isNotEmpty || pocAuthToken.isNotEmpty) {
      throw StateError(
        'API_BASE_URL and POC_AUTH_TOKEN are forbidden in demo mode.',
      );
    }
    return AppRuntimeConfig.demo(demoScenario: parseScenario(scenario));
  }

  static Uri _parseBaseUri(String value) {
    if (value.trim().isEmpty) {
      throw StateError('API_BASE_URL is required for networked modes.');
    }
    final uri = Uri.tryParse(value.trim());
    if (uri == null) {
      throw StateError('API_BASE_URL must be a valid absolute HTTP(S) URI.');
    }
    return uri;
  }

  static Uri _validateBaseUri(Uri uri, {required bool requireHttps}) {
    final scheme = uri.scheme.toLowerCase();
    final hasRootPath = uri.path.isEmpty || uri.path == '/';
    if (!uri.isAbsolute ||
        uri.host.isEmpty ||
        !{'http', 'https'}.contains(scheme) ||
        uri.userInfo.isNotEmpty ||
        uri.hasQuery ||
        uri.hasFragment ||
        !hasRootPath) {
      throw StateError(
        'API_BASE_URL must be an absolute HTTP(S) origin without credentials, '
        'path, query, or fragment.',
      );
    }
    if (requireHttps && scheme != 'https') {
      throw StateError('API_BASE_URL must use HTTPS in production.');
    }
    return uri.replace(path: '');
  }

  static String _validatePocToken(String value) {
    if (value.isEmpty) {
      throw StateError('POC_AUTH_TOKEN is required in networked modes.');
    }
    if (RegExp(r'[\x00-\x20\x7F]').hasMatch(value)) {
      throw StateError(
        'POC_AUTH_TOKEN must not contain whitespace or control characters.',
      );
    }
    return value;
  }
}
