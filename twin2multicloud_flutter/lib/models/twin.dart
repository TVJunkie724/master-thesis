class Twin {
  final String id;
  final String name;
  final String state;
  final List<String> providers;
  final DateTime? createdAt;
  final DateTime? updatedAt;
  final DateTime? lastDeployedAt;
  final DateTime? deployedAt;
  final DateTime? destroyedAt;
  final String? lastError;

  Twin({
    required this.id,
    required this.name,
    required this.state,
    required this.providers,
    this.createdAt,
    this.updatedAt,
    this.lastDeployedAt,
    this.deployedAt,
    this.destroyedAt,
    this.lastError,
  });

  factory Twin.fromJson(Map<String, dynamic> json) {
    return Twin(
      id: json['id'],
      name: json['name'],
      state: json['state'] ?? 'draft',
      providers: List<String>.from(json['providers'] ?? []),
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : null,
      updatedAt: json['updated_at'] != null
          ? DateTime.parse(json['updated_at'])
          : null,
      lastDeployedAt: json['last_deployed_at'] != null
          ? DateTime.parse(json['last_deployed_at'])
          : null,
      deployedAt: json['deployed_at'] != null
          ? DateTime.parse(json['deployed_at'])
          : null,
      destroyedAt: json['destroyed_at'] != null
          ? DateTime.parse(json['destroyed_at'])
          : null,
      lastError: json['last_error'] as String?,
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
}
