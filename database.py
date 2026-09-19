import aiosqlite
from config import DATABASE_PATH


async def init_db() -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price_stars INTEGER NOT NULL CHECK (price_stars > 0),
                price_uah INTEGER CHECK (price_uah IS NULL OR price_uah > 0),
                photo TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                items_json TEXT NOT NULL,
                total_stars INTEGER NOT NULL CHECK (total_stars > 0),
                total_uah INTEGER CHECK (total_uah IS NULL OR total_uah > 0),
                payment_method TEXT,
                delivery TEXT NOT NULL,
                delivery_cost INTEGER NOT NULL DEFAULT 0,
                customer_name TEXT,
                customer_phone TEXT,
                customer_address TEXT,
                customer_comment TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                channel_message_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS cart (
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, product_id)
            );
            """
        )
        columns = {row[1] for row in await (await db.execute("PRAGMA table_info(products)")).fetchall()}
        if "price_uah" not in columns:
            await db.execute("ALTER TABLE products ADD COLUMN price_uah INTEGER")
        order_columns = {row[1] for row in await (await db.execute("PRAGMA table_info(orders)")).fetchall()}
        if "total_uah" not in order_columns:
            await db.execute("ALTER TABLE orders ADD COLUMN total_uah INTEGER")
        if "payment_method" not in order_columns:
            await db.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT")
        await db.commit()


async def add_user(user_id: int, username: str | None, full_name: str | None) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (user_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                full_name = excluded.full_name
            """,
            (user_id, username, full_name),
        )
        await db.commit()


async def get_products() -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM products ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_product(product_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def add_product(name: str, description: str, price_stars: int, price_uah: int | None, photo: str | None) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO products (name, description, price_stars, price_uah, photo) VALUES (?, ?, ?, ?, ?)",
            (name, description, price_stars, price_uah, photo),
        )
        await db.commit()
        return cursor.lastrowid


async def delete_product(product_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await db.commit()


async def add_to_cart(user_id: int, product_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        existing = await cursor.fetchone()
        if existing:
            await db.execute(
                "UPDATE cart SET quantity = quantity + 1 WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            )
        else:
            await db.execute(
                "INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1)",
                (user_id, product_id),
            )
        await db.commit()


async def get_cart(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT
                cart.quantity,
                products.id AS product_id,
                products.name,
                products.price_stars,
                products.price_uah,
                products.photo
            FROM cart
            JOIN products ON products.id = cart.product_id
            WHERE cart.user_id = ?
            ORDER BY products.name
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def set_cart_quantity(user_id: int, product_id: int, quantity: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        if quantity <= 0:
            await db.execute(
                "DELETE FROM cart WHERE user_id = ? AND product_id = ?",
                (user_id, product_id),
            )
        else:
            await db.execute(
                "UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?",
                (quantity, user_id, product_id),
            )
        await db.commit()


async def remove_from_cart(user_id: int, product_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "DELETE FROM cart WHERE user_id = ? AND product_id = ?",
            (user_id, product_id),
        )
        await db.commit()


async def clear_cart(user_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        await db.commit()


async def create_order(
    *,
    user_id: int,
    items_json: str,
    total_stars: int,
    total_uah: int | None,
    payment_method: str | None,
    delivery: str,
    delivery_cost: int,
    customer_name: str,
    customer_phone: str,
    customer_address: str,
    customer_comment: str,
) -> int:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            """
            INSERT INTO orders (
                user_id, items_json, total_stars, total_uah, payment_method, delivery, delivery_cost,
                customer_name, customer_phone, customer_address,
                customer_comment, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                user_id,
                items_json,
                total_stars,
                total_uah,
                payment_method,
                delivery,
                delivery_cost,
                customer_name,
                customer_phone,
                customer_address,
                customer_comment,
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def get_order(order_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_orders(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_order_status(order_id: int, status: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        await db.commit()


async def update_channel_message(order_id: int, channel_message_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE orders SET channel_message_id = ? WHERE id = ?",
            (channel_message_id, order_id),
        )
        await db.commit()


async def add_admin(user_id: int) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
        await db.commit()


async def update_order_payment_method(order_id: int, payment_method: str) -> None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("UPDATE orders SET payment_method = ? WHERE id = ?", (payment_method, order_id))
        await db.commit()
