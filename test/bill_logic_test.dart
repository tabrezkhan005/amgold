import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:amgold/core/utils/currency.dart';
import 'package:amgold/features/bill/bill_controller.dart';
import 'package:amgold/features/bill/bill_repository.dart';
import 'package:amgold/models/bill_item.dart';
import 'package:amgold/models/product.dart';

Product _product(String id, double price) => Product(
      id: id,
      code: 'AMG-$id',
      name: 'Item $id',
      category: 'necklace',
      material: 'rolled_gold',
      price: price,
      weightG: 10,
      description: 'PLACEHOLDER',
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('BillDraft totals use price snapshots', () {
    final draft = BillDraft(
      items: [
        BillItem(product: _product('P001', 450), quantity: 2, unitPrice: 450),
        BillItem(product: _product('P002', 100), quantity: 1, unitPrice: 99),
      ],
      discount: 50,
    );
    expect(draft.itemCount, 3);
    expect(draft.subtotal, 999);
    expect(draft.total, 949);
  });

  test('invoice numbers increment per day', () async {
    SharedPreferences.setMockInitialValues({});
    final repo = BillRepository();
    final day = DateTime(2026, 10, 26);
    final a = await repo.nextInvoiceNo(when: day);
    final b = await repo.nextInvoiceNo(when: day);
    expect(a, 'AMG-20261026-001');
    expect(b, 'AMG-20261026-002');
  });

  test('formatInr uses rupee and Indian grouping', () {
    final formatted = formatInr(123456.0);
    expect(formatted.contains('\u20B9'), isTrue);
    expect(formatted.contains('1,23,456'), isTrue);
  });
}
