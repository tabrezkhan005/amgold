// Bill draft history from GET /v1/bills/drafts (status from desk relay).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_colors.dart';
import '../../models/bill_draft_remote.dart';
import '../../widgets/error_view.dart';

final _dateFmt = DateFormat('dd MMM yyyy, hh:mm a');

final draftHistoryProvider = FutureProvider<List<BillDraftRemote>>((ref) async {
  return ref.watch(apiClientProvider).listBillDrafts(limit: 50);
});

class BillHistoryScreen extends ConsumerWidget {
  const BillHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(draftHistoryProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Bill history'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: () => ref.invalidate(draftHistoryProvider),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorView(
          message: e is ApiException ? e.message : e.toString(),
          onRetry: () => ref.invalidate(draftHistoryProvider),
        ),
        data: (drafts) {
          if (drafts.isEmpty) {
            return const Center(child: Text('No drafts sent yet'));
          }
          return ListView.separated(
            itemCount: drafts.length,
            separatorBuilder: (context, index) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final d = drafts[i];
              final when = d.createdAt;
              return ListTile(
                title: Text(
                  d.customerName?.isNotEmpty == true
                      ? d.customerName!
                      : 'Draft ${d.id.substring(0, 8)}…',
                ),
                subtitle: Text(
                  '${when != null ? _dateFmt.format(when.toLocal()) : '—'}'
                  ' · ${d.itemCount} item(s)'
                  '${d.deskInvoiceRef != null ? ' · ${d.deskInvoiceRef}' : ''}'
                  '${d.failureReason != null ? ' · ${d.failureReason}' : ''}',
                ),
                trailing: _StatusChip(status: d.status, label: d.statusLabel),
              );
            },
          );
        },
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status, required this.label});

  final String status;
  final String label;

  @override
  Widget build(BuildContext context) {
    final Color bg;
    switch (status) {
      case 'imported':
        bg = Colors.green.shade100;
      case 'failed':
        bg = Colors.red.shade100;
      case 'delivered':
        bg = Colors.blue.shade100;
      case 'cancelled':
        bg = Colors.grey.shade300;
      default:
        bg = AppColors.gold.withValues(alpha: 0.25);
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        label,
        style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
      ),
    );
  }
}
