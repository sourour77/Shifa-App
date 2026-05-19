from ai_module.Chatbot import PRODUCT_KNOWLEDGE, QUANTITY_OFFERS, BUNDLE_OFFERS
from ai_module.product_db import upsert_product, upsert_bundle_offer


for name, product in PRODUCT_KNOWLEDGE.items():
    product = product.copy()
    product["quantity_offers"] = QUANTITY_OFFERS.get(name, [])
    upsert_product(product)
    print(f"Inserted product: {name}")


for bundle in BUNDLE_OFFERS:
    upsert_bundle_offer(bundle)
    print(f"Inserted bundle: {bundle.get('title')}")

print("Done.")