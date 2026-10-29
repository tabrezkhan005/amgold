// Shop header placeholders for PDF invoices (replace before demo if needed).
class ShopConfig {
  const ShopConfig({
    required this.name,
    required this.address,
    required this.phone,
  });

  final String name;
  final String address;
  final String phone;

  static const ShopConfig current = ShopConfig(
    name: 'AmGold Ornaments',
    address: 'PLACEHOLDER - Shop address, City, PIN',
    phone: 'PLACEHOLDER - +91 XXXXX XXXXX',
  );
}
