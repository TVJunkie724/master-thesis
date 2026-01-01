import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/user.dart';
import 'theme_provider.dart';

// Mocked user for development - now includes theme preference
final mockUser = User(
  id: "mock-user-123",
  email: "developer@example.com",
  name: "Developer",
  pictureUrl: null,
  themePreference: "dark",
);

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier(ref);
});

class AuthState {
  final User? user;
  final bool isLoading;
  final bool isAuthenticated;
  
  AuthState({this.user, this.isLoading = false, this.isAuthenticated = false});
}

class AuthNotifier extends StateNotifier<AuthState> {
  final Ref _ref;
  
  AuthNotifier(this._ref) : super(AuthState());
  
  // MOCK: Auto-login for development
  Future<void> mockLogin() async {
    state = AuthState(isLoading: true);
    await Future.delayed(const Duration(milliseconds: 500)); // Simulate delay
    state = AuthState(user: mockUser, isAuthenticated: true);
    
    // Hydrate theme from user's preference
    _ref.read(themeProvider.notifier).hydrateFromUser(mockUser.themePreference);
  }
  
  /// Login with user data from API (for real OAuth flows)
  void loginWithUser(User user) {
    state = AuthState(user: user, isAuthenticated: true);
    
    // Hydrate theme from user's preference
    _ref.read(themeProvider.notifier).hydrateFromUser(user.themePreference);
  }
  
  void logout() {
    state = AuthState();
  }
}
