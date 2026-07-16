import 'user.dart';

enum IdentityProvider {
  uibk('uibk', 'UIBK'),
  google('google', 'Google');

  const IdentityProvider(this.apiValue, this.defaultDisplayName);

  final String apiValue;
  final String defaultDisplayName;

  static IdentityProvider parse(Object? value) => switch (value) {
    'uibk' => IdentityProvider.uibk,
    'google' => IdentityProvider.google,
    _ => throw const FormatException(
      'Invalid authentication provider contract.',
    ),
  };
}

class AuthProviderCapability {
  const AuthProviderCapability({
    required this.provider,
    required this.displayName,
    required this.enabled,
    this.unavailableReason,
  });

  final IdentityProvider provider;
  final String displayName;
  final bool enabled;
  final String? unavailableReason;

  factory AuthProviderCapability.fromJson(Map<String, dynamic> json) {
    final displayName = json['display_name'];
    final enabled = json['enabled'];
    final unavailableReason = json['unavailable_reason'];
    if (displayName is! String ||
        displayName.trim().isEmpty ||
        enabled is! bool) {
      throw const FormatException(
        'Invalid authentication capability contract.',
      );
    }
    if (unavailableReason != null && unavailableReason is! String) {
      throw const FormatException(
        'Invalid authentication capability reason contract.',
      );
    }
    return AuthProviderCapability(
      provider: IdentityProvider.parse(json['provider']),
      displayName: displayName.trim(),
      enabled: enabled,
      unavailableReason: unavailableReason as String?,
    );
  }
}

class AuthLoginTransaction {
  const AuthLoginTransaction({
    required this.authUri,
    required this.transactionId,
    required this.pollVerifier,
    required this.expiresAt,
    required this.pollInterval,
  });

  final Uri authUri;
  final String transactionId;
  final String pollVerifier;
  final DateTime expiresAt;
  final Duration pollInterval;

  factory AuthLoginTransaction.fromJson(Map<String, dynamic> json) {
    final authUri = Uri.tryParse(json['auth_url']?.toString() ?? '');
    final transactionId = json['transaction_id'];
    final pollVerifier = json['poll_verifier'];
    final expiresAt = DateTime.tryParse(json['expires_at']?.toString() ?? '');
    final pollIntervalMs = json['poll_interval_ms'];
    final canonicalUuid = RegExp(
      r'^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
    );
    if (authUri == null ||
        authUri.scheme != 'https' ||
        authUri.host.isEmpty ||
        transactionId is! String ||
        !canonicalUuid.hasMatch(transactionId) ||
        pollVerifier is! String ||
        pollVerifier.length < 32 ||
        expiresAt == null ||
        pollIntervalMs is! int ||
        pollIntervalMs < 500 ||
        pollIntervalMs > 5000) {
      throw const FormatException('Invalid authentication start contract.');
    }
    return AuthLoginTransaction(
      authUri: authUri,
      transactionId: transactionId,
      pollVerifier: pollVerifier,
      expiresAt: expiresAt.toUtc(),
      pollInterval: Duration(milliseconds: pollIntervalMs),
    );
  }

  Map<String, String> toCommandJson() => {
    'transaction_id': transactionId,
    'poll_verifier': pollVerifier,
  };
}

sealed class AuthExchangeResult {
  const AuthExchangeResult();

  factory AuthExchangeResult.fromJson(Map<String, dynamic> json) {
    return switch (json['status']) {
      'pending' => const AuthExchangePending(),
      'authenticated' => _authenticated(json),
      _ => throw const FormatException(
        'Invalid authentication exchange contract.',
      ),
    };
  }

  static AuthExchangeAuthenticated _authenticated(Map<String, dynamic> json) {
    final token = json['access_token'];
    final tokenType = json['token_type'];
    final expiresIn = json['expires_in'];
    final user = json['user'];
    if (token is! String ||
        token.isEmpty ||
        RegExp(r'[\x00-\x20\x7F]').hasMatch(token) ||
        tokenType != 'bearer' ||
        expiresIn is! int ||
        expiresIn <= 0 ||
        user is! Map) {
      throw const FormatException('Invalid authenticated session contract.');
    }
    return AuthExchangeAuthenticated(
      accessToken: token,
      expiresIn: Duration(seconds: expiresIn),
      user: User.fromJson(Map<String, dynamic>.from(user)),
    );
  }
}

class AuthExchangePending extends AuthExchangeResult {
  const AuthExchangePending();
}

class AuthExchangeAuthenticated extends AuthExchangeResult {
  const AuthExchangeAuthenticated({
    required this.accessToken,
    required this.expiresIn,
    required this.user,
  });

  final String accessToken;
  final Duration expiresIn;
  final User user;
}
