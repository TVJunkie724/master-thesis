import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/user.dart';
import '../utils/api_error_handler.dart';
import 'runtime_providers.dart';
import 'theme_provider.dart';

final profileProvider = NotifierProvider<ProfileNotifier, ProfileState>(
  ProfileNotifier.new,
);

enum ProfilePhase { loading, available, error }

class ProfileState {
  const ProfileState({required this.phase, this.user, this.errorMessage});

  const ProfileState.loading() : this(phase: ProfilePhase.loading);

  final ProfilePhase phase;
  final User? user;
  final String? errorMessage;

  bool get isAvailable => user != null;
  bool get isLoading => phase == ProfilePhase.loading;
}

class ProfileNotifier extends Notifier<ProfileState> {
  bool _disposed = false;
  int _requestGeneration = 0;

  @override
  ProfileState build() {
    _disposed = false;
    final initialUser = ref.watch(initialUserProvider);
    if (initialUser != null) {
      return ProfileState(phase: ProfilePhase.available, user: initialUser);
    }

    final api = ref.watch(apiServiceProvider);
    api.setUnauthorizedHandler(_handleUnauthorizedProfile);
    ref.onDispose(() {
      _disposed = true;
      _requestGeneration++;
      api.setUnauthorizedHandler(null);
    });
    unawaited(Future<void>.microtask(loadProfile));
    return const ProfileState.loading();
  }

  Future<void> loadProfile() async {
    final generation = ++_requestGeneration;
    state = const ProfileState.loading();
    try {
      final user = await ref.read(apiServiceProvider).getCurrentUser();
      if (!_isCurrent(generation)) return;
      state = ProfileState(phase: ProfilePhase.available, user: user);
      ref.read(themeProvider.notifier).hydrateFromUser(user.themePreference);
    } catch (error) {
      if (!_isCurrent(generation)) return;
      state = ProfileState(
        phase: ProfilePhase.error,
        errorMessage: _safeProfileError(error),
      );
    }
  }

  void _handleUnauthorizedProfile() {
    if (_disposed) return;
    _requestGeneration++;
    state = const ProfileState(
      phase: ProfilePhase.error,
      errorMessage:
          'The local PoC profile could not be authorized. Check the runtime '
          'configuration and restart the application.',
    );
  }

  bool _isCurrent(int generation) =>
      !_disposed && generation == _requestGeneration;

  static String _safeProfileError(Object error) {
    if (error is DioException) return ApiErrorHandler.extractMessage(error);
    if (error is FormatException) {
      return 'The Management API returned an invalid local profile.';
    }
    return 'The local PoC profile could not be loaded.';
  }
}
