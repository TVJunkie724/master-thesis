class User {
  final String id;
  final String email;
  final String? name;
  final String? pictureUrl;
  final String authProvider;  // "google" | "uibk"
  final bool uibkLinked;
  final bool googleLinked;

  User({
    required this.id,
    required this.email,
    this.name,
    this.pictureUrl,
    this.authProvider = "google",
    this.uibkLinked = false,
    this.googleLinked = false,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'],
      email: json['email'],
      name: json['name'],
      pictureUrl: json['picture_url'],
      authProvider: json['auth_provider'] ?? 'google',
      uibkLinked: json['uibk_linked'] ?? false,
      googleLinked: json['google_linked'] ?? false,
    );
  }
}

