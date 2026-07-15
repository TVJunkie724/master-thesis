import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/app_logger.dart';
import '../services/management_api.dart';
import 'runtime_providers.dart';

final themeProvider = NotifierProvider<ThemeNotifier, ThemeMode>(
  ThemeNotifier.new,
);

class ThemeNotifier extends Notifier<ThemeMode> {
  static const _storageKey = 'theme_preference';
  late final UserPreferencesApi _api;
  Timer? _debounceTimer;

  @override
  ThemeMode build() {
    _api = ref.read(apiServiceProvider);
    final runtime = ref.read(appRuntimeProvider);
    final initialUser = ref.read(initialUserProvider);
    if (runtime.isDemo && initialUser != null) {
      return initialUser.themePreference == 'light'
          ? ThemeMode.light
          : ThemeMode.dark;
    }
    _loadFromStorage();
    ref.onDispose(() {
      _debounceTimer?.cancel();
    });
    return ThemeMode.dark;
  }

  /// Load theme from local storage immediately on app start
  Future<void> _loadFromStorage() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString(_storageKey);
    if (stored != null) {
      state = stored == 'light' ? ThemeMode.light : ThemeMode.dark;
    }
  }

  /// Hydrate theme from user object after login (from API)
  void hydrateFromUser(String? themePreference) {
    if (themePreference != null) {
      state = themePreference == 'light' ? ThemeMode.light : ThemeMode.dark;
      _saveToStorage(themePreference);
    }
  }

  /// Toggle theme - saves locally and syncs to API (debounced)
  void toggle() {
    state = state == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    final themeName = state == ThemeMode.dark ? 'dark' : 'light';

    // Save locally immediately
    _saveToStorage(themeName);

    // Debounce API sync (500ms)
    _debounceTimer?.cancel();
    _debounceTimer = Timer(const Duration(milliseconds: 500), () {
      _syncToApi(themeName);
    });
  }

  void setTheme(ThemeMode mode) {
    state = mode;
    final themeName = mode == ThemeMode.dark ? 'dark' : 'light';
    _saveToStorage(themeName);
    _syncToApi(themeName);
  }

  Future<void> _saveToStorage(String theme) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_storageKey, theme);
  }

  Future<void> _syncToApi(String theme) async {
    try {
      await _api.updateUserPreferences(themePreference: theme);
    } catch (_) {
      const AppLogger().warning(AppLogEvent.themePreferenceSyncFailed);
    }
  }
}
