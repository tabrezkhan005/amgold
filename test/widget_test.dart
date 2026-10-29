import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:amgold/features/auth/auth_controller.dart';
import 'package:amgold/features/auth/enroll_screen.dart';
import 'package:amgold/features/auth/login_screen.dart';

class _SettledAuth extends AuthController {
  _SettledAuth(this._initial);

  final AuthState _initial;

  @override
  AuthState build() => _initial;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Enroll screen builds', (WidgetTester tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(
            () => _SettledAuth(
              const AuthState(isLoading: false, isEnrolled: false),
            ),
          ),
        ],
        child: const MaterialApp(home: EnrollScreen()),
      ),
    );
    await tester.pump();
    expect(find.text('AmGold'), findsOneWidget);
    expect(find.text('Enroll device'), findsOneWidget);
  });

  testWidgets('Login screen builds with PIN field', (WidgetTester tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider.overrideWith(
            () => _SettledAuth(
              const AuthState(
                isLoading: false,
                isEnrolled: true,
                isLoggedIn: false,
                deviceLabel: 'Shop phone',
              ),
            ),
          ),
        ],
        child: const MaterialApp(home: LoginScreen()),
      ),
    );
    await tester.pump();
    expect(find.text('AmGold'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);
    expect(find.text('PIN'), findsOneWidget);
  });
}
