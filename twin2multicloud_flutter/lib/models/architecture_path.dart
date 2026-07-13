class ArchitecturePath {
  static const _providers = {'AWS', 'AZURE', 'GCP'};
  static const _storageTiers = {'HOT', 'COOL', 'ARCHIVE'};

  static String? providerForSegment(String segment) {
    final parts = segment
        .split('_')
        .map((part) => part.trim().toUpperCase())
        .toList(growable: false);
    if (parts.length < 2) return null;
    for (final part in parts.skip(1)) {
      if (_providers.contains(part)) return part;
    }
    return null;
  }

  static String? storageTierForSegment(String segment) {
    if (!segment.toUpperCase().startsWith('L3_')) return null;
    for (final part in segment.split('_').skip(1)) {
      final normalized = part.trim().toUpperCase();
      if (_storageTiers.contains(normalized)) return normalized.toLowerCase();
    }
    return null;
  }

  static Map<String, String> layerProviders(List<String> path) {
    final result = <String, String>{};
    for (final segment in path) {
      final parts = segment.split('_');
      if (parts.isEmpty) continue;
      final provider = providerForSegment(segment);
      if (provider != null) result[parts.first.toUpperCase()] = provider;
    }
    return result;
  }
}
