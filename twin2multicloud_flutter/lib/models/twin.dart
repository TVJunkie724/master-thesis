import 'package:equatable/equatable.dart';

import 'json_contract.dart';

class Twin extends Equatable {
  static const supportedStates = {
    'draft',
    'configured',
    'deploying',
    'deployed',
    'destroying',
    'destroyed',
    'error',
    'inactive',
  };

  final String id;
  final String name;
  final String state;
  final List<String> providers;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime? lastDeployedAt;
  final DateTime? deployedAt;
  final DateTime? destroyedAt;
  final String? lastError;
  final String? lastDeploymentLogs;

  const Twin({
    required this.id,
    required this.name,
    required this.state,
    required this.createdAt,
    required this.updatedAt,
    this.providers = const [],
    this.lastDeployedAt,
    this.deployedAt,
    this.destroyedAt,
    this.lastError,
    this.lastDeploymentLogs,
  });

  factory Twin.fromJson(Map<String, dynamic> json) {
    final state = JsonContract.requiredString(json, 'state');
    if (!supportedStates.contains(state)) {
      throw const FormatException(
        'Invalid API contract: state contains an unknown twin state.',
      );
    }
    final deployedAt = JsonContract.optionalDate(json, 'deployed_at');
    return Twin(
      id: JsonContract.requiredString(json, 'id'),
      name: JsonContract.requiredString(json, 'name'),
      state: state,
      providers: JsonContract.optionalStringList(json, 'providers'),
      createdAt: JsonContract.requiredDate(json, 'created_at'),
      updatedAt: JsonContract.requiredDate(json, 'updated_at'),
      lastDeployedAt:
          JsonContract.optionalDate(json, 'last_deployed_at') ?? deployedAt,
      deployedAt: deployedAt,
      destroyedAt: JsonContract.optionalDate(json, 'destroyed_at'),
      lastError: JsonContract.optionalString(json, 'last_error'),
      lastDeploymentLogs: JsonContract.optionalString(
        json,
        'last_deployment_logs',
      ),
    );
  }

  // State helpers
  bool get isDraft => state == 'draft';
  bool get isConfigured => state == 'configured';
  bool get isDeploying => state == 'deploying';
  bool get isDeployed => state == 'deployed';
  bool get isDestroying => state == 'destroying';
  bool get isDestroyed => state == 'destroyed';
  bool get isError => state == 'error';

  @override
  List<Object?> get props => [
    id,
    name,
    state,
    providers,
    createdAt,
    updatedAt,
    lastDeployedAt,
    deployedAt,
    destroyedAt,
    lastError,
    lastDeploymentLogs,
  ];
}
