// INR formatting with en_IN grouping and rupee symbol.
import 'package:intl/intl.dart';

final NumberFormat _inr = NumberFormat.currency(
  locale: 'en_IN',
  symbol: '\u20B9',
  decimalDigits: 2,
);

String formatInr(num amount) => _inr.format(amount);
