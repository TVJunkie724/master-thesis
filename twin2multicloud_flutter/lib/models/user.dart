class User {
  final String id;
  final String email;
  final String? name;
  final String themePreference; // "light" | "dark"

  User({
    required this.id,
    required this.email,
    this.name,
    this.themePreference = "dark",
  });

  factory User.fromJson(Map<String, dynamic> json) {
    final id = json['id'];
    final email = json['email'];
    final name = json['name'];
    final themePreference = json['theme_preference'];
    if (id is! String ||
        id.isEmpty ||
        email is! String ||
        !email.contains('@') ||
        (name != null && name is! String) ||
        (themePreference != null &&
            !const {'light', 'dark'}.contains(themePreference))) {
      throw const FormatException('Invalid user contract.');
    }
    return User(
      id: id,
      email: email,
      name: name as String?,
      themePreference: themePreference as String? ?? 'dark',
    );
  }
}
