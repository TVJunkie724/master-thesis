import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/dashboard_stats.dart';
import '../models/cloud_connection.dart';
import '../models/pricing_review_state.dart';
import '../models/twin.dart';
import '../services/api_service.dart';

final apiServiceProvider = Provider((ref) => ApiService());

final twinsProvider = FutureProvider<List<Twin>>((ref) async {
  final api = ref.read(apiServiceProvider);

  // Fetch twins from database via Management API
  final data = await api.getTwins();
  return data
      .map((json) => Twin.fromJson(json as Map<String, dynamic>))
      .toList();
});

/// Dashboard statistics provider.
///
/// Tries the dedicated /dashboard/stats endpoint first (includes cost data).
/// Falls back to computing counts from the twins list if the endpoint fails.
final dashboardStatsProvider = FutureProvider<DashboardStats>((ref) async {
  final api = ref.read(apiServiceProvider);
  try {
    return await api.getDashboardStats();
  } catch (_) {
    // Fallback: compute counts from twins list (cost unavailable)
    final twins = await ref.read(twinsProvider.future);
    return DashboardStats.fromTwins(twins);
  }
});

final pricingReviewStateProvider =
    FutureProvider.family<PricingReviewStateResponse, String?>((ref, twinId) {
      final api = ref.read(apiServiceProvider);
      return api.getPricingReviewState(twinId);
    });

final cloudConnectionsProvider = FutureProvider<List<CloudConnection>>((
  ref,
) async {
  final api = ref.read(apiServiceProvider);
  return api.listCloudConnections();
});
