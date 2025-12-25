import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/user.dart';

// Mocked user for development
final mockUser = User(
  id: "mock-user-123",
  email: "developer@example.com",
  name: "Developer",
  pictureUrl: null,
);

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier();
});

class AuthState {
  final User? user;
  final bool isLoading;
  final bool isAuthenticated;
  
  AuthState({this.user, this.isLoading = false, this.isAuthenticated = false});
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(AuthState());
  
  // MOCK: Auto-login for development
  Future<void> mockLogin() async {
    state = AuthState(isLoading: true);
    await Future.delayed(const Duration(milliseconds: 500)); // Simulate delay
    state = AuthState(user: mockUser, isAuthenticated: true);
  }
  
  void logout() {
    state = AuthState();
  }
}
