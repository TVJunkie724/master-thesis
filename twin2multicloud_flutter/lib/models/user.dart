class User {
  final String id;
  final String email;
  final String? name;
  final String? pictureUrl;

  User({
    required this.id,
    required this.email,
    this.name,
    this.pictureUrl,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'],
      email: json['email'],
      name: json['name'],
      pictureUrl: json['picture_url'],
    );
  }
}
