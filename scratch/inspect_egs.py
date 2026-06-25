import urllib.request
import json
import sys

url = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions?locale=ru&country=RU"
req = urllib.request.Request(
    url,
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
)

output_lines = []

try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode("utf-8"))
        
    elements = data["data"]["Catalog"]["searchStore"]["elements"]
    output_lines.append(f"Всего элементов в ответе: {len(elements)}\n")
    
    for el in elements:
        title = el.get("title")
        price = el.get("price", {})
        total_price = price.get("totalPrice", {})
        fmt_price = total_price.get("fmtPrice", {})
        discount_price = fmt_price.get("discountPrice", "")
        original_price = fmt_price.get("originalPrice", "")
        
        # Промоакции
        promotions = el.get("promotions")
        has_promotions = promotions is not None
        
        # Ищем, бесплатная ли игра по цене
        is_free_by_price = total_price.get("discountPrice") == 0
        
        output_lines.append(f"Название: {title}")
        output_lines.append(f"  Цена: оригинал={original_price}, со скидкой={discount_price}, число={total_price.get('discountPrice')}")
        output_lines.append(f"  Есть промоакции: {has_promotions}")
        
        if has_promotions:
            promo_offers = promotions.get("promotionalOffers", [])
            upcoming_offers = promotions.get("upcomingPromotionalOffers", [])
            output_lines.append(f"  Промоакции (активные): {len(promo_offers)}")
            if promo_offers:
                for group in promo_offers:
                    for offer in group.get("promotionalOffers", []):
                        ds = offer.get("discountSetting", {})
                        output_lines.append(f"    - Скидка: тип={ds.get('discountType')}, значение={ds.get('discountValue')}, процент={ds.get('discountPercentage')}, даты={offer.get('startDate')} -> {offer.get('endDate')}")
            print(f"  Промоакции (будущие): {len(upcoming_offers)}")
            if upcoming_offers:
                for group in upcoming_offers:
                    for offer in group.get("promotionalOffers", []):
                        ds = offer.get("discountSetting", {})
                        output_lines.append(f"    - Скидка: тип={ds.get('discountType')}, значение={ds.get('discountValue')}, процент={ds.get('discountPercentage')}, даты={offer.get('startDate')} -> {offer.get('endDate')}")
        output_lines.append("-" * 50)
        
    with open("egs_inspect.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print("Результат успешно записан в egs_inspect.txt")
        
except Exception as e:
    print(f"Ошибка: {e}")
