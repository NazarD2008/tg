import asyncio
import json
import logging
from typing import Any

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from config import ADMIN_IDS, BOT_TOKEN, CHANNEL_DEST, DELIVERY_METHODS
from database import (
    add_admin,
    add_product,
    add_to_cart,
    clear_cart,
    create_order,
    delete_product,
    get_cart,
    get_order,
    get_orders,
    get_product,
    get_products,
    init_db,
    remove_from_cart,
    set_cart_quantity,
    update_order_status,
    add_user,
)
from keyboards import (
    add_product_confirm_keyboard,
    admin_products_keyboard,
    cart_keyboard,
    delivery_keyboard,
    main_menu_keyboard,
    products_keyboard,
    product_keyboard,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


class Checkout(StatesGroup):
    name = State()
    phone = State()
    address = State()
    comment = State()
    delivery = State()


class AddProduct(StatesGroup):
    name = State()
    price = State()
    description = State()
    photo = State()
    confirm = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def cart_total(items: list[dict]) -> int:
    return sum(item["price_stars"] * item["quantity"] for item in items)


def order_text(order: dict) -> str:
    items = json.loads(order["items_json"])
    delivery = DELIVERY_METHODS.get(order["delivery"], {"name": order["delivery"]})
    lines = [
        f"📦 Новый заказ #{order['id']}",
        "",
        f"👤 Покупатель: {order['customer_name'] or '—'}",
        f"📱 Телефон: {order['customer_phone'] or '—'}",
        f"🏠 Адрес: {order['customer_address'] or '—'}",
        f"💬 Комментарий: {order['customer_comment'] or '—'}",
        f"🚚 Доставка: {delivery['name']}",
        f"💰 Итого: {order['total_stars']} ⭐",
        "",
        "Товары:",
    ]
    for item in items:
        lines.append(f"• {item['name']} ×{item['quantity']} — {item['price_stars'] * item['quantity']} ⭐")
    lines.extend(
        [
            "",
            f"Статус: {order['status']}",
            f"Время: {order['created_at']}",
        ]
    )
    return "\n".join(lines)


async def send_order_to_channel(order: dict) -> bool:
    if not CHANNEL_DEST:
        logger.warning("CHANNEL_DEST не настроен, заказ не отправлен в канал")
        return False
    try:
        await bot.send_message(CHANNEL_DEST, order_text(order))
        return True
    except Exception as exc:
        logger.error("Не удалось отправить заказ в канал: %s", exc)
        return False


async def render_catalog(message: Message, page: int = 0) -> None:
    products = await get_products()
    if not products:
        await message.answer("📦 Каталог пока пуст. Загляните позже!", reply_markup=main_menu_keyboard())
        return
    per_page = 5
    total_pages = (len(products) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    page_products = products[page * per_page:(page + 1) * per_page]
    await message.answer("📦 Каталог:", reply_markup=products_keyboard(page_products, page, total_pages))


async def render_cart(message: Message, user_id: int) -> None:
    items = await get_cart(user_id)
    if not items:
        await message.answer("🛒 Корзина пуста.", reply_markup=main_menu_keyboard())
        return
    total = cart_total(items)
    lines = ["🛒 Корзина:", ""]
    for item in items:
        lines.append(f"• {item['name']} ×{item['quantity']} — {item['price_stars'] * item['quantity']} ⭐")
    lines.extend(["", f"💰 Итого: {total} ⭐"])
    await message.answer("\n".join(lines), reply_markup=cart_keyboard(items))


async def ask_delivery(message: Message, state: FSMContext) -> None:
    await state.set_state(Checkout.delivery)
    await message.answer("Выберите способ доставки:", reply_markup=delivery_keyboard())


async def send_invoice(message: Message, order_id: int, total: int) -> None:
    await bot.send_invoice(
        chat_id=message.chat.id,
        title=f"Заказ #{order_id}",
        description=f"Оплата заказа #{order_id} в нашем магазине",
        payload=f"order:{order_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"Заказ #{order_id}", amount=total)],
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
    )


# -----------------------------
# Пользовательские команды
# -----------------------------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    text = f"Привет, {message.from_user.full_name}! 👋\n\nВыберите раздел:"
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n"
        "/start — главное меню\n"
        "/catalog — каталог\n"
        "/cart — корзина\n"
        "/cancel — отменить текущее действие\n"
        "/admin — админ-панель"
    )


@router.message(Command("catalog"))
async def cmd_catalog(message: Message) -> None:
    await render_catalog(message)


@router.message(Command("cart"))
async def cmd_cart(message: Message) -> None:
    await render_cart(message, message.from_user.id)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu_keyboard())


# -----------------------------
# Каталог и корзина
# -----------------------------

@router.callback_query(lambda callback: bool(callback.data and callback.data.startswith("catalog:")))
async def cb_catalog(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":", 1)[1])
    await render_catalog(callback.message, page)
    await callback.answer()


@router.callback_query(lambda callback: bool(callback.data and callback.data.startswith("product:")))
async def cb_product(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    product = await get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return
    text = f"📦 {product['name']}\n\n{product['description'] or 'Без описания'}\n\n💰 {product['price_stars']} ⭐"
    if product["photo"]:
        await callback.message.answer_photo(product["photo"], caption=text, reply_markup=product_keyboard(product_id))
    else:
        await callback.message.answer(text, reply_markup=product_keyboard(product_id))
    await callback.answer()


@router.callback_query(lambda callback: bool(callback.data and callback.data.startswith("add:")))
async def cb_add_to_cart(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    product = await get_product(product_id)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return
    await add_to_cart(callback.from_user.id, product_id)
    await callback.answer("Товар добавлен в корзину 🛒")


@router.callback_query(lambda callback: bool(callback.data and callback.data.startswith("cart_inc:")))
async def cb_cart_inc(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    items = await get_cart(callback.from_user.id)
    item = next((item for item in items if item["product_id"] == product_id), None)
    if item:
        await set_cart_quantity(callback.from_user.id, product_id, item["quantity"] + 1)
    await render_cart(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(lambda callback: bool(callback.data and callback.data.startswith("cart_dec:")))
async def cb_cart_dec(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    items = await get_cart(callback.from_user.id)
    item = next((item for item in items if item["product_id"] == product_id), None)
    if item:
        await set_cart_quantity(callback.from_user.id, product_id, item["quantity"] - 1)
    await render_cart(callback.message, callback.from_user.id)
    await callback.answer()


@router.callback_query(lambda callback: bool(callback.data and callback.data.startswith("cart_rm:")))
async def cb_cart_rm(callback: CallbackQuery) -> None:
    product_id = int(callback.data.split(":", 1)[1])
    await remove_from_cart(callback.from_user.id, product_id)
    await render_cart(callback.message, callback.from_user.id)
    await callback.answer("Товар удалён")


@router.callback_query(lambda callback: callback.data == "cart_clear")
async def cb_cart_clear(callback: CallbackQuery) -> None:
    await clear_cart(callback.from_user.id)
    await render_cart(callback.message, callback.from_user.id)
    await callback.answer("Корзина очищена")


@router.callback_query(lambda callback: callback.data == "main")
async def cb_main(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_keyboard())
    await callback.answer()


# -----------------------------
# Оформление заказа
# -----------------------------

@router.callback_query(lambda callback: callback.data == "checkout_start")
async def cb_checkout_start(callback: CallbackQuery, state: FSMContext) -> None:
    items = await get_cart(callback.from_user.id)
    if not items:
        await callback.answer("Корзина пуста", show_alert=True)
        return
    await state.clear()
    await state.set_state(Checkout.name)
    await callback.message.answer("Как к вам обращаться? Введите имя и фамилию:")
    await callback.answer()


@router.message(Checkout.name, F.text)
async def checkout_name(message: Message, state: FSMContext) -> None:
    await state.update(name=message.text.strip())
    await state.set_state(Checkout.phone)
    await message.answer("Введите номер телефона для связи:")


@router.message(Checkout.phone, F.text)
async def checkout_phone(message: Message, state: FSMContext) -> None:
    await state.update(phone=message.text.strip())
    await state.set_state(Checkout.address)
    await message.answer("Введите адрес доставки:")


@router.message(Checkout.address, F.text)
async def checkout_address(message: Message, state: FSMContext) -> None:
    await state.update(address=message.text.strip())
    await state.set_state(Checkout.comment)
    await message.answer("Комментарий к заказу (или отправьте /skip, если его нет):")


@router.message(Checkout.comment, Command("skip"))
async def checkout_comment_skip(message: Message, state: FSMContext) -> None:
    await state.update(comment="")
    await ask_delivery(message, state)


@router.message(Checkout.comment, F.text)
async def checkout_comment(message: Message, state: FSMContext) -> None:
    await state.update(comment=message.text.strip())
    await ask_delivery(message, state)


@router.callback_query(lambda callback: bool(callback.data and callback.data.startswith("delivery:")))
async def cb_delivery(callback: CallbackQuery, state: FSMContext) -> None:
    delivery = callback.data.split(":", 1)[1]
    if delivery not in DELIVERY_METHODS:
        await callback.answer("Неизвестный способ доставки", show_alert=True)
        return
    items = await get_cart(callback.from_user.id)
    if not items:
        await callback.answer("Корзина пуста", show_alert=True)
        return
    data = await state.get_data()
    subtotal = cart_total(items)
    delivery_cost = DELIVERY_METHODS[delivery]["cost"]
    total = subtotal + delivery_cost
    order_id = await create_order(
        user_id=callback.from_user.id,
        items_json=json.dumps(items, ensure_ascii=False),
        total_stars=total,
        delivery=delivery,
        delivery_cost=delivery_cost,
        customer_name=data.get("name", ""),
        customer_phone=data.get("phone", ""),
        customer_address=data.get("address", ""),
        customer_comment=data.get("comment", ""),
    )
    await state.update(order_id=order_id)
    await callback.message.answer(
        f"Заказ #{order_id} создан.\n"
        f"Сумма к оплате: {total} ⭐\n\n"
        "Нажмите «Заплатить» в открывшемся окне оплаты."
    )
    await send_invoice(callback.message, order_id, total)
    await callback.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await bot.answer_pre_checkout_query(query.id, ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, state: FSMContext) -> None:
    payload = message.successful_payment.invoice_payload
    if not payload.startswith("order:"):
        await message.answer("Оплата получена, но заказ не найден. Напишите администратору.")
        return
    order_id = int(payload.split(":", 1)[1])
    order = await get_order(order_id)
    if not order:
        await message.answer("Заказ не найден. Напишите администратору.")
        return
    await update_order_status(order_id, "paid")
    order = await get_order(order_id)
    await clear_cart(message.from_user.id)
    await state.clear()
    sent = await send_order_to_channel(order)
    if sent:
        await message.answer(
            f"✅ Оплата прошла успешно!\n\n"
            f"Заказ #{order_id} отправлен в канал. Мы свяжемся с вами для подтверждения доставки."
        )
    else:
        await message.answer(
            f"✅ Оплата прошла успешно!\n\n"
            f"Заказ #{order_id} сохранён, но не удалось отправить его в канал. Напишите администратору."
        )


# -----------------------------
# Админ-панель
# -----------------------------

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    await message.answer(
        "🛠 Админ-панель\n\n"
        "/add_product — добавить товар\n"
        "/products — список товаров\n"
        "/orders — последние заказы\n"
        "/set_admin — назначить администратора"
    )


@router.message(Command("add_product"))
async def cmd_add_product(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    await state.clear()
    await state.set_state(AddProduct.name)
    await message.answer("Введите название товара:")


@router.message(AddProduct.name, F.text)
async def add_product_name(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    await state.update(name=message.text.strip())
    await state.set_state(AddProduct.price)
    await message.answer("Введите цену товара в звёздах Telegram (например, 150):")


@router.message(AddProduct.price, F.text)
async def add_product_price(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    try:
        price = int(message.text.strip())
    except ValueError:
        await message.answer("Цена должна быть целым положительным числом. Введите цену ещё раз:")
        return
    if price <= 0:
        await message.answer("Цена должна быть положительной. Введите цену ещё раз:")
        return
    await state.update(price=price)
    await state.set_state(AddProduct.description)
    await message.answer("Введите описание товара (или отправьте /skip):")


@router.message(AddProduct.description, Command("skip"))
async def add_product_description_skip(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    await state.update(description="")
    await state.set_state(AddProduct.photo)
    await message.answer("Отправьте фото товара (или отправьте /skip):")


@router.message(AddProduct.description, F.text)
async def add_product_description(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    await state.update(description=message.text.strip())
    await state.set_state(AddProduct.photo)
    await message.answer("Отправьте фото товара (или отправьте /skip):")


@router.message(AddProduct.photo, Command("skip"))
async def add_product_photo_skip(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    await state.update(photo=None)
    await show_add_product_confirmation(message, state)


@router.message(AddProduct.photo, F.photo)
async def add_product_photo(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    await state.update(photo=message.photo[-1].file_id)
    await show_add_product_confirmation(message, state)


async def show_add_product_confirmation(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = (
        "Проверьте данные товара:\n\n"
        f"📦 Название: {data['name']}\n"
        f"💰 Цена: {data['price']} ⭐\n"
        f"📝 Описание: {data.get('description', '—')}\n"
        f"📸 Фото: {'будет' if data.get('photo') else 'нет'}"
    )
    await state.set_state(AddProduct.confirm)
    await message.answer(text, reply_markup=add_product_confirm_keyboard())


@router.callback_query(lambda callback: callback.data == "add_confirm")
async def cb_add_product_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return
    data = await state.get_data()
    product_id = await add_product(
        name=data["name"],
        description=data.get("description", ""),
        price_stars=data["price"],
        photo=data.get("photo"),
    )
    await state.clear()
    await callback.message.answer(f"✅ Товар #{product_id} добавлен в каталог.")
    await callback.answer("Товар добавлен")


@router.callback_query(lambda callback: callback.data == "add_cancel")
async def cb_add_product_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return
    await state.clear()
    await callback.message.answer("Добавление товара отменено.")
    await callback.answer("Отменено")


@router.message(Command("products"))
async def cmd_products(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    products = await get_products()
    if not products:
        await message.answer("Товаров пока нет.")
        return
    await message.answer("📦 Товары:", reply_markup=admin_products_keyboard(products))


@router.callback_query(lambda callback: bool(callback.data and callback.data.startswith("delete_product:")))
async def cb_delete_product(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return
    product_id = int(callback.data.split(":", 1)[1])
    await delete_product(product_id)
    await callback.message.answer(f"Товар #{product_id} удалён.")
    await callback.answer("Товар удалён")


@router.message(Command("orders"))
async def cmd_orders(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    orders = await get_orders(limit=20)
    if not orders:
        await message.answer("Заказов пока нет.")
        return
    for order in orders:
        await message.answer(order_text(order))


@router.message(Command("set_admin"))
async def cmd_set_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer("Ответьте на сообщение пользователя, которого нужно назначить администратором.")
        return
    await add_admin(message.reply_to_message.from_user.id)
    await message.answer(f"Пользователь {message.reply_to_message.from_user.id} назначен администратором.")


# -----------------------------
# Запуск
# -----------------------------

async def set_commands() -> None:
    commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="catalog", description="Открыть каталог"),
        BotCommand(command="cart", description="Корзина"),
        BotCommand(command="help", description="Справка"),
        BotCommand(command="admin", description="Админ-панель"),
        BotCommand(command="add_product", description="Добавить товар"),
        BotCommand(command="products", description="Список товаров"),
        BotCommand(command="orders", description="Последние заказы"),
    ]
    await bot.set_my_commands(commands)


async def main() -> None:
    await init_db()
    await set_commands()
    dp.include_router(router)
    logger.info("Бот запускается...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
