import pymysql
from contextlib import contextmanager
from config import Config


@contextmanager
def get_conn():
    conn = pymysql.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        port=Config.DB_PORT,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=5,
    )
    try:
        yield conn
    finally:
        conn.close()


def get_all_products():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM products ORDER BY id")
        return cur.fetchall()


def get_product(product_id):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM products WHERE id=%s", (product_id,))
        return cur.fetchone()


def get_products_by_ids(ids):
    if not ids:
        return []
    with get_conn() as conn, conn.cursor() as cur:
        fmt = ",".join(["%s"] * len(ids))
        cur.execute(f"SELECT * FROM products WHERE id IN ({fmt})", tuple(ids))
        return cur.fetchall()


def create_order(customer_name, customer_email, shipping_address, total_amount, items, user_id=None):
    """items: list of dicts {id, qty, price}"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO orders (user_id, customer_name, customer_email, shipping_address, total_amount, status)
               VALUES (%s, %s, %s, %s, %s, 'PENDING')""",
            (user_id, customer_name, customer_email, shipping_address, total_amount),
        )
        order_id = cur.lastrowid
        for item in items:
            cur.execute(
                """INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                   VALUES (%s, %s, %s, %s)""",
                (order_id, item["id"], item["qty"], item["price"]),
            )
        return order_id


def get_order(order_id):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM orders WHERE id=%s", (order_id,))
        order = cur.fetchone()
        if not order:
            return None
        cur.execute(
            """SELECT oi.*, p.name FROM order_items oi
               JOIN products p ON p.id = oi.product_id
               WHERE oi.order_id=%s""",
            (order_id,),
        )
        order["items"] = cur.fetchall()
        return order


def get_orders_by_user(user_id):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM orders WHERE user_id=%s ORDER BY created_at DESC",
            (user_id,),
        )
        return cur.fetchall()


def get_all_orders():
    """For the admin dashboard - most recent first."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM orders ORDER BY created_at DESC")
        return cur.fetchall()


def update_order_status(order_id, status):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE orders SET status=%s WHERE id=%s", (status, order_id))
