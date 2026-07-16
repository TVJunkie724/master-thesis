abstract interface class ExternalAuthLaunchHandle {
  Future<bool> navigate(Uri uri);

  Future<void> close();
}

abstract interface class ExternalAuthLauncher {
  ExternalAuthLaunchHandle reserve();
}
