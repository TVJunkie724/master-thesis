abstract interface class ExternalAuthLaunchHandle {
  Future<bool> navigate(Uri uri);

  Future<bool> renderHtml(String html);

  Future<void> close();
}

abstract interface class ExternalAuthLauncher {
  ExternalAuthLaunchHandle reserve();
}
