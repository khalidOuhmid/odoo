# Diagnostic script for lot filtering
print("\n" + "="*60)
print("DIAGNOSTIC: Product Lot Category Assignment")
print("="*60)

# Check lot categories
categories = env['construction.lot.category'].search([])
print(f"\n[1] Lot Categories in system: {len(categories)}")
for cat in categories:
    print(f"    - ID: {cat.id}, Code: {cat.code}, Name: {cat.name}")

# Check products with lot_category_id set
products_with_cat = env['product.template'].search([('lot_category_id', '!=', False)])
print(f"\n[2] Products with lot_category_id SET: {len(products_with_cat)}")
for p in products_with_cat[:5]:
    print(f"    - {p.name}: lot_category_id = {p.lot_category_id.name if p.lot_category_id else 'None'}")

# Check products WITHOUT lot_category_id
products_without = env['product.template'].search([('lot_category_id', '=', False), ('sale_ok', '=', True)])
print(f"\n[3] Saleable products WITHOUT lot_category_id: {len(products_without)}")
for p in products_without[:5]:
    print(f"    - {p.name}")

# Check if category_id=2 exists
cat_2 = env['construction.lot.category'].browse(2)
print(f"\n[4] Category ID=2: {cat_2.name if cat_2.exists() else 'NOT FOUND'}")

# Products with category_id=2
products_cat_2 = env['product.template'].search([('lot_category_id', '=', 2)])
print(f"\n[5] Products with lot_category_id=2: {len(products_cat_2)}")

print("\n" + "="*60)
print("CONCLUSION: Assign lot_category_id to products to enable filtering")
print("="*60 + "\n")
