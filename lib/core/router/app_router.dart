// go_router: enroll → login → scan; settings; auth guards.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/auth_controller.dart';
import '../../features/auth/enroll_screen.dart';
import '../../features/auth/login_screen.dart';
import '../../features/bill/bill_history_screen.dart';
import '../../features/bill/bill_screen.dart';
import '../../features/owner/add_product_screen.dart';
import '../../features/product/product_detail_screen.dart';
import '../../features/results/results_screen.dart';
import '../../features/scan/scan_screen.dart';
import '../../features/search/manual_search_screen.dart';
import '../../features/settings/settings_screen.dart';

final _routerRefreshProvider = Provider<ValueNotifier<int>>((ref) {
  final notifier = ValueNotifier(0);
  ref.listen(authControllerProvider, (_, _) {
    notifier.value++;
  });
  ref.onDispose(notifier.dispose);
  return notifier;
});

final appRouterProvider = Provider<GoRouter>((ref) {
  final refresh = ref.watch(_routerRefreshProvider);

  return GoRouter(
    initialLocation: '/enroll',
    refreshListenable: refresh,
    redirect: (context, state) {
      final auth = ref.read(authControllerProvider);
      if (auth.isLoading) return null;

      final loc = state.matchedLocation;
      final onEnroll = loc == '/enroll';
      final onLogin = loc == '/login';

      if (!auth.isEnrolled) {
        return onEnroll ? null : '/enroll';
      }
      if (!auth.isLoggedIn) {
        if (onLogin || onEnroll) return null;
        return '/login';
      }
      if (onEnroll || onLogin) return '/scan';
      return null;
    },
    routes: [
      GoRoute(
        path: '/enroll',
        builder: (context, state) => const EnrollScreen(),
      ),
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/scan',
        builder: (context, state) => const ScanScreen(),
      ),
      GoRoute(
        path: '/results',
        builder: (context, state) => const ResultsScreen(),
      ),
      GoRoute(
        path: '/product/:id',
        builder: (context, state) => ProductDetailScreen(
          productId: state.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/search',
        builder: (context, state) => const ManualSearchScreen(),
      ),
      GoRoute(
        path: '/bill',
        builder: (context, state) => const BillScreen(),
      ),
      GoRoute(
        path: '/history',
        builder: (context, state) => const BillHistoryScreen(),
      ),
      GoRoute(
        path: '/settings',
        builder: (context, state) => const SettingsScreen(),
      ),
      GoRoute(
        path: '/owner/add-product',
        builder: (context, state) => const AddProductScreen(),
      ),
    ],
  );
});
