import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/twin.dart';
import '../services/api_service.dart';

final apiServiceProvider = Provider((ref) => ApiService());

final twinsProvider = FutureProvider<List<Twin>>((ref) async {
  final api = ref.read(apiServiceProvider);
  
  // Fetch twins from database via Management API
  final data = await api.getTwins();
  return data.map((json) => Twin.fromJson(json as Map<String, dynamic>)).toList();
});
