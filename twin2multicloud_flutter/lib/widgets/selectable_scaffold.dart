import 'package:flutter/material.dart';

/// Drop-in replacement for [Scaffold] that wraps the entire screen in a
/// [SelectionArea], making all text within (AppBar titles, body content,
/// dialogs invoked from this screen, snackbars, etc.) user-selectable.
///
/// Use this instead of [Scaffold] in screen widgets so users can copy
/// error messages, credentials, log output, and other text that would
/// otherwise be locked.
///
/// Why not wrap the whole app at [MaterialApp.builder]?
/// `MaterialApp.router`'s builder runs above the Navigator, which means
/// [SelectionArea] would have no [Overlay] ancestor — required by its
/// internal [SelectableRegion] for the selection toolbar — and crashes
/// at startup.
class SelectableScaffold extends StatelessWidget {
  const SelectableScaffold({
    super.key,
    this.appBar,
    this.body,
    this.floatingActionButton,
    this.floatingActionButtonLocation,
    this.bottomNavigationBar,
    this.backgroundColor,
    this.drawer,
    this.endDrawer,
    this.resizeToAvoidBottomInset,
    this.extendBody = false,
    this.extendBodyBehindAppBar = false,
    this.persistentFooterButtons,
    this.bottomSheet,
  });

  final PreferredSizeWidget? appBar;
  final Widget? body;
  final Widget? floatingActionButton;
  final FloatingActionButtonLocation? floatingActionButtonLocation;
  final Widget? bottomNavigationBar;
  final Color? backgroundColor;
  final Widget? drawer;
  final Widget? endDrawer;
  final bool? resizeToAvoidBottomInset;
  final bool extendBody;
  final bool extendBodyBehindAppBar;
  final List<Widget>? persistentFooterButtons;
  final Widget? bottomSheet;

  @override
  Widget build(BuildContext context) {
    return SelectionArea(
      child: Scaffold(
        appBar: appBar,
        body: body,
        floatingActionButton: floatingActionButton,
        floatingActionButtonLocation: floatingActionButtonLocation,
        bottomNavigationBar: bottomNavigationBar,
        backgroundColor: backgroundColor,
        drawer: drawer,
        endDrawer: endDrawer,
        resizeToAvoidBottomInset: resizeToAvoidBottomInset,
        extendBody: extendBody,
        extendBodyBehindAppBar: extendBodyBehindAppBar,
        persistentFooterButtons: persistentFooterButtons,
        bottomSheet: bottomSheet,
      ),
    );
  }
}
