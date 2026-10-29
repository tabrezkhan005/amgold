// Local bill persistence and invoice counters.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../models/bill.dart';
import '../../models/bill_item.dart';
import 'bill_controller.dart';

const _kBillsKey = 'amgold_saved_bills';
const _kInvoiceCounterPrefix = 'amgold_invoice_counter_';

class BillRepository {
  Future<String> nextInvoiceNo({DateTime? when}) async {
    final now = when ?? DateTime.now();
    final day =
        '${now.year.toString().padLeft(4, '0')}${now.month.toString().padLeft(2, '0')}${now.day.toString().padLeft(2, '0')}';
    final prefs = await SharedPreferences.getInstance();
    final key = '$_kInvoiceCounterPrefix$day';
    final next = (prefs.getInt(key) ?? 0) + 1;
    await prefs.setInt(key, next);
    final nnn = next.toString().padLeft(3, '0');
    return 'AMG-$day-$nnn';
  }

  Future<List<Bill>> loadBills() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_kBillsKey) ?? const [];
    final bills = <Bill>[];
    for (final line in raw) {
      try {
        bills.add(Bill.fromJson(jsonDecode(line) as Map<String, dynamic>));
      } catch (_) {
        // Skip corrupt entries.
      }
    }
    bills.sort((a, b) => b.createdAt.compareTo(a.createdAt));
    return bills;
  }

  Future<void> saveBill(Bill bill) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getStringList(_kBillsKey) ?? <String>[];
    existing.insert(0, jsonEncode(bill.toJson()));
    await prefs.setStringList(_kBillsKey, existing);

    try {
      final dir = await getApplicationDocumentsDirectory();
      final billsDir = Directory('${dir.path}/bills');
      if (!await billsDir.exists()) {
        await billsDir.create(recursive: true);
      }
      final file = File('${billsDir.path}/${bill.invoiceNo}.json');
      await file.writeAsString(jsonEncode(bill.toJson()));
    } catch (_) {
      // SharedPreferences remains the source of truth for history.
    }
  }

  Bill draftToBill(BillDraft draft, String invoiceNo) {
    return Bill(
      invoiceNo: invoiceNo,
      createdAt: DateTime.now(),
      customerName: draft.customerName,
      customerPhone: draft.customerPhone,
      items: List<BillItem>.from(draft.items),
      discount: draft.discount,
    );
  }
}

final billRepositoryProvider = Provider<BillRepository>((ref) {
  return BillRepository();
});

final savedBillsProvider = FutureProvider<List<Bill>>((ref) async {
  return ref.watch(billRepositoryProvider).loadBills();
});
