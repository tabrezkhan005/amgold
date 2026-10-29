// Online / offline banner via connectivity_plus.
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final connectivityProvider = StreamProvider<List<ConnectivityResult>>((ref) {
  return Connectivity().onConnectivityChanged;
});

final isOfflineProvider = Provider<bool>((ref) {
  final async = ref.watch(connectivityProvider);
  return async.when(
    data: (results) {
      if (results.isEmpty) return true;
      return results.every((r) => r == ConnectivityResult.none);
    },
    loading: () => false,
    error: (_, _) => false,
  );
});
