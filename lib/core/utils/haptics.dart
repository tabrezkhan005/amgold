// Haptic feedback helpers for capture and add-to-bill.
import 'package:flutter/services.dart';

Future<void> hapticCapture() => HapticFeedback.mediumImpact();

Future<void> hapticAddToBill() => HapticFeedback.lightImpact();
