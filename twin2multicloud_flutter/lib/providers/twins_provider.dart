import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/twin.dart';
import '../services/api_service.dart';

final apiServiceProvider = Provider((ref) => ApiService());

final twinsProvider = FutureProvider<List<Twin>>((ref) async {
  // ignore: unused_local_variable
  final api = ref.read(apiServiceProvider);
  
  // For now, return mock data (swap to real API when backend is running)
  // final data = await api.getTwins();
  // return data.map((json) => Twin.fromJson(json)).toList();
  
  // MOCK DATA for development
  return [
    Twin(id: '1', name: 'Smart Home', state: 'deployed', providers: ['AWS', 'Azure']),
    Twin(id: '2', name: 'Factory Floor', state: 'configured', providers: ['GCP']),
    Twin(id: '3', name: 'Office HVAC', state: 'error', providers: ['AWS']),
    Twin(id: '4', name: 'Test Project', state: 'draft', providers: []),
  ];
});
