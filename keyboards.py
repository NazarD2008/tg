from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import DELIVERY_METHODS


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Каталог", callback_data="catalog:0")],
            [InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")],
        ]
    )


def products_keyboard(products: list[dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows = []
    for product in products:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{product['name']} — {product['price_uah']} ₴ / {product['price_stars']}⭐" if product.get('price_uah') else f"{product['name']} — {product['price_stars']}⭐",
                    callback_data=f"product:{product['id']}",
                )
            ]
        )
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"catalog:{page - 1}"))
    if page < total_pages - 1:
        navigation.append(InlineKeyboardButton(text="▶️ Далее", callback_data=f"catalog:{page + 1}"))
    if navigation:
        rows.append(navigation)
    rows.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_keyboard(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Добавить в корзину", callback_data=f"add:{product_id}")],
            [InlineKeyboardButton(text="◀️ В каталог", callback_data="catalog:0")],
        ]
    )


def cart_keyboard(items: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for item in items:
        rows.append(
            [
                InlineKeyboardButton(text="−", callback_data=f"cart_dec:{item['product_id']}"),
                InlineKeyboardButton(
                    text=f"{item['name']} ×{item['quantity']}",
                    callback_data=f"product:{item['product_id']}",
                ),
                InlineKeyboardButton(text="+", callback_data=f"cart_inc:{item['product_id']}"),
            ]
        )
        rows.append([InlineKeyboardButton(text="🗑 Удалить", callback_data=f"cart_rm:{item['product_id']}")])
    rows.append([InlineKeyboardButton(text="✅ Оформить заказ", callback_data="checkout_start")])
    rows.append([InlineKeyboardButton(text="🗑 Очистить", callback_data="cart_clear")])
    rows.append([InlineKeyboardButton(text="◀️ Каталог", callback_data="catalog:0")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delivery_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for key, method in DELIVERY_METHODS.items():
        suffix = f" +{method['cost_uah']} ₴ / {method['cost_stars']}⭐" if method["cost_uah"] or method["cost_stars"] else ""
        rows.append([InlineKeyboardButton(text=f"{method['name']}{suffix}", callback_data=f"delivery:{key}")])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="cart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_products_keyboard(products: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for product in products:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 {product['name']} ({product['price_stars']}⭐)",
                    callback_data=f"delete_product:{product['id']}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="➕ Добавить товар", callback_data="add_start")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def add_product_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Добавить", callback_data="add_confirm")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="add_cancel")],
        ]
    )


def payment_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перевод на карту", callback_data="pay:card")],
        [InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="pay:stars")],
    ])


def card_payment_admin_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"card_paid:{order_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"card_reject:{order_id}")],
    ])
