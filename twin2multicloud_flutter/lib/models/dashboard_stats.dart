import 'package:equatable/equatable.dart';

import 'twin.dart';

class DashboardStats extends Equatable {
  final int deployedCount;
  final int draftCount;
  final int totalTwins;
  final double estimatedMonthlyCost;

  const DashboardStats({
    required this.deployedCount,
    required this.draftCount,
    required this.totalTwins,
    required this.estimatedMonthlyCost,
  });

  factory DashboardStats.fromJson(Map<String, dynamic> json) {
    return DashboardStats(
      deployedCount: _readInt(json, 'deployed_count'),
      draftCount: _readInt(json, 'draft_count'),
      totalTwins: _readInt(json, 'total_twins'),
      estimatedMonthlyCost: _readDouble(json, 'estimated_monthly_cost'),
    );
  }

  factory DashboardStats.fromTwins(List<Twin> twins) {
    return DashboardStats(
      deployedCount: twins.where((twin) => twin.isDeployed).length,
      draftCount: twins.where((twin) => twin.isDraft).length,
      totalTwins: twins.length,
      estimatedMonthlyCost: 0,
    );
  }

  static const empty = DashboardStats(
    deployedCount: 0,
    draftCount: 0,
    totalTwins: 0,
    estimatedMonthlyCost: 0,
  );

  @override
  List<Object?> get props => [
    deployedCount,
    draftCount,
    totalTwins,
    estimatedMonthlyCost,
  ];
}

int _readInt(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value) ?? 0;
  return 0;
}

double _readDouble(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value) ?? 0;
  return 0;
}
