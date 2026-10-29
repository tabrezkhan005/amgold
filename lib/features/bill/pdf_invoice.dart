// A4 PDF invoice using bundled Noto Sans for the rupee symbol.
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

import '../../core/config/shop_config.dart';
import '../../core/utils/currency.dart';
import '../../models/bill.dart';

final DateFormat _dateFmt = DateFormat('dd MMM yyyy, hh:mm a');

Future<pw.ThemeData> _invoiceTheme() async {
  final regular = await rootBundle.load('assets/fonts/NotoSans-Regular.ttf');
  final bold = await rootBundle.load('assets/fonts/NotoSans-Bold.ttf');
  return pw.ThemeData.withFont(
    base: pw.Font.ttf(regular),
    bold: pw.Font.ttf(bold),
  );
}

Future<Uint8List> buildInvoicePdf(
  Bill bill, {
  ShopConfig shop = ShopConfig.current,
}) async {
  final theme = await _invoiceTheme();
  final doc = pw.Document(theme: theme);

  doc.addPage(
    pw.MultiPage(
      pageFormat: PdfPageFormat.a4,
      margin: const pw.EdgeInsets.all(40),
      build: (context) => [
        pw.Text(
          shop.name,
          style: pw.TextStyle(fontSize: 22, fontWeight: pw.FontWeight.bold),
        ),
        pw.SizedBox(height: 4),
        pw.Text(shop.address, style: const pw.TextStyle(fontSize: 10)),
        pw.Text(shop.phone, style: const pw.TextStyle(fontSize: 10)),
        pw.SizedBox(height: 16),
        pw.Divider(),
        pw.SizedBox(height: 8),
        pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          children: [
            pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                pw.Text(
                  'Invoice',
                  style: pw.TextStyle(
                    fontSize: 16,
                    fontWeight: pw.FontWeight.bold,
                  ),
                ),
                pw.Text(bill.invoiceNo),
                pw.Text(_dateFmt.format(bill.createdAt)),
              ],
            ),
            pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.end,
              children: [
                pw.Text(
                  'Customer',
                  style: pw.TextStyle(fontWeight: pw.FontWeight.bold),
                ),
                pw.Text(
                  bill.customerName.isEmpty ? '—' : bill.customerName,
                ),
                pw.Text(
                  bill.customerPhone.isEmpty ? '—' : bill.customerPhone,
                ),
              ],
            ),
          ],
        ),
        pw.SizedBox(height: 20),
        pw.TableHelper.fromTextArray(
          headers: const ['Item', 'Material', 'Qty', 'Unit', 'Line total'],
          data: [
            for (final item in bill.items)
              [
                item.product.name,
                item.product.materialLabel,
                '${item.quantity}',
                formatInr(item.unitPrice),
                formatInr(item.lineTotal),
              ],
          ],
          headerStyle: pw.TextStyle(fontWeight: pw.FontWeight.bold),
          headerDecoration: const pw.BoxDecoration(color: PdfColors.grey300),
          cellStyle: const pw.TextStyle(fontSize: 10),
          cellAlignment: pw.Alignment.centerLeft,
          cellAlignments: {
            2: pw.Alignment.centerRight,
            3: pw.Alignment.centerRight,
            4: pw.Alignment.centerRight,
          },
        ),
        pw.SizedBox(height: 16),
        pw.Align(
          alignment: pw.Alignment.centerRight,
          child: pw.SizedBox(
            width: 220,
            child: pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.stretch,
              children: [
                _totalRow('Subtotal', formatInr(bill.subtotal)),
                if (bill.discount > 0)
                  _totalRow('Discount', '- ${formatInr(bill.discount)}'),
                pw.Divider(),
                _totalRow(
                  'Indicative total',
                  formatInr(bill.total),
                  bold: true,
                ),
              ],
            ),
          ),
        ),
        pw.SizedBox(height: 28),
        pw.Text(
          'Items are sold as labelled (e.g. rolled gold). This document does not claim items are real gold.',
          style: const pw.TextStyle(fontSize: 9, color: PdfColors.grey700),
        ),
        pw.SizedBox(height: 4),
        pw.Text(
          'Phone fallback only — final tax and totals are calculated at the billing desk.',
          style: const pw.TextStyle(fontSize: 9, color: PdfColors.grey700),
        ),
        pw.SizedBox(height: 8),
        pw.Text(
          'Thank you for your business.',
          style: const pw.TextStyle(fontSize: 10),
        ),
      ],
    ),
  );

  return doc.save();
}

pw.Widget _totalRow(String label, String value, {bool bold = false}) {
  final style = bold
      ? pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 12)
      : const pw.TextStyle(fontSize: 11);
  return pw.Padding(
    padding: const pw.EdgeInsets.symmetric(vertical: 2),
    child: pw.Row(
      mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
      children: [
        pw.Text(label, style: style),
        pw.Text(value, style: style),
      ],
    ),
  );
}

Future<void> shareInvoicePdf(Bill bill) async {
  final bytes = await buildInvoicePdf(bill);
  await Printing.sharePdf(bytes: bytes, filename: '${bill.invoiceNo}.pdf');
}

Future<void> printInvoicePdf(Bill bill) async {
  final bytes = await buildInvoicePdf(bill);
  await Printing.layoutPdf(onLayout: (_) async => bytes);
}
