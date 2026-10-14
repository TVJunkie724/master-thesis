import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/twin.dart';
import '../models/twin_transfer.dart';
import 'runtime_providers.dart';

export 'runtime_providers.dart'
    show apiServiceProvider, logStreamClientFactoryProvider;

final twinsProvider = FutureProvider<List<Twin>>((ref) async {
  final api = ref.read(apiServiceProvider);
  return api.getTwins();
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
      state = const AsyncData(null);
    } catch (error, stackTrace) {
      state = AsyncError(error, stackTrace);
      rethrow;
    }
  }

  Future<Twin?> duplicateTwin(String twinId, TwinDuplicateRequest request) =>
      _runTwinMutation(
        () => ref.read(apiServiceProvider).duplicateTwin(twinId, request),
      );

  Future<Twin?> importTwin(TwinImportRequest request) =>
      _runTwinMutation(() => ref.read(apiServiceProvider).importTwin(request));

  Future<PortableTwinDownload?> exportTwin(String twinId) async {
    if (state.isLoading) return null;

    state = const AsyncLoading();
    try {
      final download = await ref.read(apiServiceProvider).exportTwin(twinId);
      state = const AsyncData(null);
      return download;
    } catch (error, stackTrace) {
      state = AsyncError(error, stackTrace);
      rethrow;
    }
  }

  Future<Twin?> _runTwinMutation(Future<Twin> Function() command) async {
    if (state.isLoading) return null;

    state = const AsyncLoading();
    try {
      final twin = await command();
      ref.invalidate(twinsProvider);
      state = const AsyncData(null);
      return twin;
    } catch (error, stackTrace) {
      state = AsyncError(error, stackTrace);
      rethrow;
    }
  }
}
