enum AppMode { development, production, demo }

enum DemoScenario { showcase, empty, degraded }

class AppRuntimeConfig {
  final AppMode mode;
  final DemoScenario demoScenario;

  const AppRuntimeConfig({
    required this.mode,
    this.demoScenario = DemoScenario.showcase,
  });

  factory AppRuntimeConfig.fromEnvironment() {
    const modeValue = String.fromEnvironment(
      'APP_MODE',
      defaultValue: 'development',
    );
    const scenarioValue = String.fromEnvironment(
      'DEMO_SCENARIO',
      defaultValue: 'showcase',
    );

    return AppRuntimeConfig(
      mode: parseMode(modeValue),
      demoScenario: parseScenario(scenarioValue),
    );
  }

  bool get isDemo => mode == AppMode.demo;

  static AppMode parseMode(String value) {
    return switch (value.trim().toLowerCase()) {
      'development' || 'dev' => AppMode.development,
      'production' || 'prod' => AppMode.production,
      'demo' => AppMode.demo,
      _ => throw StateError(
        'Unsupported APP_MODE "$value". '
        'Expected development, production, or demo.',
      ),
    };
  }

  static DemoScenario parseScenario(String value) {
    return switch (value.trim().toLowerCase()) {
      'showcase' => DemoScenario.showcase,
      'empty' => DemoScenario.empty,
      'degraded' => DemoScenario.degraded,
      _ => throw StateError(
        'Unsupported DEMO_SCENARIO "$value". '
        'Expected showcase, empty, or degraded.',
      ),
    };
  }
}
