class ApiConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:5005',
  );

  static const String devAuthToken = String.fromEnvironment(
    'DEV_AUTH_TOKEN',
    defaultValue: 'dev-token',
  );
}
