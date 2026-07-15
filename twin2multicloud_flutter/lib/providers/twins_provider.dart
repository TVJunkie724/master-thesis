import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/dashboard_stats.dart';
import '../models/pricing_health.dart';
import '../models/twin.dart';
import 'runtime_providers.dart';

export 'runtime_providers.dart'
    show apiServiceProvider, logStreamClientFactoryProvider;

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

final pricingHealthProvider = FutureProvider<PricingHealthResponse>((ref) {
  return ref.read(apiServiceProvider).getPricingHealth();
});

final twinCommandProvider =
    NotifierProvider<TwinCommandController, AsyncValue<void>>(
      TwinCommandController.new,
    );

class TwinCommandController extends Notifier<AsyncValue<void>> {
  @override
  AsyncValue<void> build() => const AsyncData(null);

  Future<void> deleteTwin(String twinId) async {
    if (state.isLoading) return;

    state = const AsyncLoading();
    try {
      await ref.read(apiServiceProvider).deleteTwin(twinId);
      ref.invalidate(twinsProvider);
      ref.invalidate(dashboardStatsProvider);
      state = const AsyncData(null);
    } catch (error, stackTrace) {
      state = AsyncError(error, stackTrace);
      rethrow;
    }
  }
}
