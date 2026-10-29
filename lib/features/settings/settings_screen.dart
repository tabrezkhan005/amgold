// Settings: user, device, version, health, logout; optional PDF fallback.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../../core/config/app_config.dart';
import '../../core/network/api_client.dart';
import '../../core/theme/app_colors.dart';
import '../../widgets/primary_button.dart';
import '../auth/auth_controller.dart';
import '../bill/bill_controller.dart';
import '../bill/bill_repository.dart';
import '../bill/pdf_invoice.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  PackageInfo? _info;
  bool? _healthOk;
  bool _healthBusy = false;
  bool _pdfBusy = false;

  @override
  void initState() {
    super.initState();
    PackageInfo.fromPlatform().then((info) {
      if (mounted) setState(() => _info = info);
    });
  }

  Future<void> _checkHealth() async {
    setState(() {
      _healthBusy = true;
      _healthOk = null;
    });
    final ok = await ref.read(apiClientProvider).healthOk();
    if (!mounted) return;
    setState(() {
      _healthOk = ok;
      _healthBusy = false;
    });
  }

  Future<void> _exportLastBillPdf() async {
    final draft = ref.read(billControllerProvider);
    if (draft.items.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Current bill is empty. Add items first, or use bill history after send.'),
        ),
      );
      return;
    }
    setState(() => _pdfBusy = true);
    try {
      final repo = ref.read(billRepositoryProvider);
      final invoiceNo = await repo.nextInvoiceNo();
      final bill = repo.draftToBill(draft, invoiceNo);
      await shareInvoicePdf(bill);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('PDF failed: $e')),
      );
    } finally {
      if (mounted) setState(() => _pdfBusy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authControllerProvider);
    final user = auth.user;

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [
          Text('Account', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(user?.displayName ?? '—'),
            subtitle: Text(
              '${user?.username ?? ''} · ${user?.role ?? ''}',
            ),
          ),
          const Divider(),
          Text('Device', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(auth.deviceLabel ?? '—'),
            subtitle: Text(
              auth.deviceId == null
                  ? 'Not enrolled'
                  : 'ID: ${auth.deviceId}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          const Divider(),
          Text('App', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(
              _info == null
                  ? '…'
                  : 'Version ${_info!.version} (${_info!.buildNumber})',
            ),
            subtitle: Text(
              AppConfig.hasApiBaseUrl
                  ? AppConfig.apiBaseUrl
                  : 'API_BASE_URL not set',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: _healthBusy ? null : _checkHealth,
                  child: _healthBusy
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Check backend'),
                ),
              ),
              const SizedBox(width: 12),
              if (_healthOk != null)
                Icon(
                  _healthOk! ? Icons.check_circle : Icons.error,
                  color: _healthOk! ? Colors.green : AppColors.error,
                ),
            ],
          ),
          const SizedBox(height: 24),
          Text(
            'Fallback',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 4),
          Text(
            'Prefer Send to billing desk. PDF is only a local fallback; '
            'final tax and totals are calculated at the desk.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: _pdfBusy ? null : _exportLastBillPdf,
            child: Text(_pdfBusy ? 'Preparing…' : 'Export current bill as PDF'),
          ),
          const SizedBox(height: 32),
          PrimaryButton(
            label: 'Sign out',
            onPressed: () async {
              await ref.read(authControllerProvider.notifier).logout();
              if (context.mounted) context.go('/login');
            },
          ),
          const SizedBox(height: 8),
          TextButton(
            onPressed: () async {
              final ok = await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Clear device enrollment?'),
                  content: const Text(
                    'You will need a new enrollment code to use this phone again.',
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(ctx, false),
                      child: const Text('Cancel'),
                    ),
                    FilledButton(
                      onPressed: () => Navigator.pop(ctx, true),
                      child: const Text('Clear'),
                    ),
                  ],
                ),
              );
              if (ok == true) {
                await ref
                    .read(authControllerProvider.notifier)
                    .logout(clearDevice: true);
                if (context.mounted) context.go('/enroll');
              }
            },
            child: const Text('Clear enrollment'),
          ),
        ],
      ),
    );
  }
}
