// Root MaterialApp / ProviderScope wiring for AmGold.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';

class AmGoldApp extends ConsumerWidget {
  const AmGoldApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(appRouterProvider);
    return MaterialApp.router(
      title: 'AmGold',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.build(useDark: false),
      darkTheme: AppTheme.build(useDark: true),
      themeMode: ThemeMode.light,
      routerConfig: router,
    );
  }
}
