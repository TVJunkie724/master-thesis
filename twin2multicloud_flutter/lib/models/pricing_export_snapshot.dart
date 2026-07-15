import 'package:equatable/equatable.dart';

import 'cloud_connection.dart';
import 'json_contract.dart';

class PricingExportSnapshot extends Equatable {
  final CloudProvider provider;
  final Map<String, dynamic> payload;
  final DateTime updatedAt;

  const PricingExportSnapshot({
    required this.provider,
    required this.payload,
    required this.updatedAt,
  });

  factory PricingExportSnapshot.fromJson(Map<String, dynamic> json) {
    final providerValue = JsonContract.requiredString(json, 'provider');
    final CloudProvider provider;
    try {
      provider = CloudProvider.fromApiValue(providerValue);
    } on ArgumentError {
      throw const FormatException(
        'Invalid API contract: provider contains an unknown provider.',
      );
    }
    return PricingExportSnapshot(
      provider: provider,
      payload: JsonContract.requiredObject(json, 'pricing'),
      updatedAt: JsonContract.requiredDate(json, 'updated_at'),
    );
  }

  @override
  List<Object?> get props => [provider, payload, updatedAt];
}
