class Twin {
  final String id;
  final String name;
  final String state;
  final List<String> providers;
  final DateTime? createdAt;
  final DateTime? updatedAt;
  final DateTime? lastDeployedAt;

  Twin({
    required this.id,
    required this.name,
    required this.state,
    required this.providers,
    this.createdAt,
    this.updatedAt,
    this.lastDeployedAt,
  });

  factory Twin.fromJson(Map<String, dynamic> json) {
    return Twin(
      id: json['id'],
      name: json['name'],
      state: json['state'] ?? 'draft',
      providers: List<String>.from(json['providers'] ?? []),
      createdAt: json['created_at'] != null ? DateTime.parse(json['created_at']) : null,
      updatedAt: json['updated_at'] != null ? DateTime.parse(json['updated_at']) : null,
      lastDeployedAt: json['last_deployed_at'] != null ? DateTime.parse(json['last_deployed_at']) : null,
    );
  }

  // State helpers
  bool get isDraft => state == 'draft';
  bool get isConfigured => state == 'configured';
  bool get isDeployed => state == 'deployed';
  bool get isError => state == 'error';
}
