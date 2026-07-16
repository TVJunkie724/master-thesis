class User {
  final String id;
  final String email;
  final String? name;
  final String? pictureUrl;
  final String authProvider; // "google" | "uibk"
  final bool uibkLinked;
  final bool googleLinked;
  final String themePreference; // "light" | "dark"

  User({
    required this.id,
    required this.email,
    this.name,
    this.pictureUrl,
    this.authProvider = "google",
    this.uibkLinked = false,
    this.googleLinked = false,
    this.themePreference = "dark",
  });

  factory User.fromJson(Map<String, dynamic> json) {
    final id = json['id'];
    final email = json['email'];
    final name = json['name'];
    final pictureUrl = json['picture_url'];
    final authProvider = json['auth_provider'];
    final uibkLinked = json['uibk_linked'];
    final googleLinked = json['google_linked'];
    final themePreference = json['theme_preference'];
    if (id is! String ||
        id.isEmpty ||
        email is! String ||
        !email.contains('@') ||
        (name != null && name is! String) ||
        (pictureUrl != null && pictureUrl is! String) ||
        (authProvider != null && authProvider is! String) ||
        (uibkLinked != null && uibkLinked is! bool) ||
        (googleLinked != null && googleLinked is! bool) ||
        (themePreference != null &&
            !const {'light', 'dark'}.contains(themePreference))) {
      throw const FormatException('Invalid user contract.');
    }
    return User(
      id: id,
      email: email,
      name: name as String?,
      pictureUrl: pictureUrl as String?,
      authProvider: authProvider as String? ?? 'development',
      uibkLinked: uibkLinked as bool? ?? false,
      googleLinked: googleLinked as bool? ?? false,
      themePreference: themePreference as String? ?? 'dark',
    );
  }
}
