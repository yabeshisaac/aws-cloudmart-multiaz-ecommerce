from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from decimal import Decimal

from config import Config
import db
import s3_utils
import sqs_utils
import auth_utils

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

PUBLIC_ROUTES = {"login", "signup", "confirm", "healthz", "static", "index", "product_detail", "view_cart", "add_to_cart", "update_cart", "remove_from_cart"}


@app.before_request
def require_login():
    if request.endpoint is None:
        return
    if request.endpoint in PUBLIC_ROUTES:
        return
    if not session.get("user_id"):
        return redirect(url_for("login", next=request.path))



# ---------- Cart helpers (cart lives in the signed session cookie) ----------

def get_cart():
    return session.get("cart", {})  # {product_id_str: qty}


def save_cart(cart):
    session["cart"] = cart
    session.modified = True


def cart_item_count(cart):
    return sum(cart.values())


# ---------- Auth decorators ----------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in first.")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in first.")
            return redirect(url_for("login", next=request.path))
        if not session.get("is_admin"):
            return render_template("404.html"), 404
        return f(*args, **kwargs)
    return wrapper


# ---------- Auth routes ----------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not (username and email and password):
            flash("Please fill in all fields.")
            return render_template("signup.html")

        try:
            auth_utils.sign_up(username, password, email)
            flash("Account created. Check your email for a confirmation code.")
            return redirect(url_for("confirm", username=email))
        except Exception as e:
            flash(f"Signup failed: {e}")
            return render_template("signup.html")

    return render_template("signup.html")


@app.route("/confirm", methods=["GET", "POST"])
def confirm():
    username = request.args.get("username", "") or request.form.get("username", "")
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        try:
            auth_utils.confirm_sign_up(username, code)
            flash("Account confirmed. You can now log in.")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"Confirmation failed: {e}")

    return render_template("confirm.html", username=username)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            result = auth_utils.login(username, password)
            id_token = result["IdToken"]
            claims = auth_utils.verify_token(id_token)

            if not claims:
                flash("Login failed: invalid token.")
                return render_template("login.html")

            session["user_id"] = claims["sub"]
            session["username"] = claims.get("cognito:username", username)
            session["is_admin"] = auth_utils.is_admin(claims)

            next_url = request.args.get("next")
            if next_url:
                return redirect(next_url)
            if session.get("is_admin"):
                return redirect(url_for("admin_orders"))
            return redirect(url_for("index"))

        except Exception as e:
            flash(f"Login failed: {e}")
            return render_template("login.html")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------- Product / cart routes ----------

@app.route("/")
def index():
    products = db.get_all_products()
    for p in products:
        p["image_url"] = s3_utils.get_presigned_url(p.get("image_key"))
    cart = get_cart()
    return render_template("index.html", products=products, cart_count=cart_item_count(cart))


@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = db.get_product(product_id)
    if not product:
        return render_template("404.html"), 404
    product["image_url"] = s3_utils.get_presigned_url(product.get("image_key"))
    cart = get_cart()
    return render_template("product.html", product=product, cart_count=cart_item_count(cart))


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    qty = max(1, int(request.form.get("qty", 1)))
    cart = get_cart()
    key = str(product_id)
    cart[key] = cart.get(key, 0) + qty
    save_cart(cart)
    flash("Added to cart.")
    return redirect(request.referrer or url_for("index"))


@app.route("/cart/update/<int:product_id>", methods=["POST"])
def update_cart(product_id):
    qty = int(request.form.get("qty", 0))
    cart = get_cart()
    key = str(product_id)
    if qty <= 0:
        cart.pop(key, None)
    else:
        cart[key] = qty
    save_cart(cart)
    return redirect(url_for("view_cart"))


@app.route("/cart/remove/<int:product_id>")
def remove_from_cart(product_id):
    cart = get_cart()
    cart.pop(str(product_id), None)
    save_cart(cart)
    return redirect(url_for("view_cart"))


@app.route("/cart")
def view_cart():
    cart = get_cart()
    ids = [int(pid) for pid in cart.keys()]
    products = db.get_products_by_ids(ids)
    for p in products:
        p["image_url"] = s3_utils.get_presigned_url(p.get("image_key"))
        p["qty"] = cart[str(p["id"])]
        p["subtotal"] = Decimal(p["price"]) * p["qty"]
    total = sum((p["subtotal"] for p in products), Decimal("0.00"))
    return render_template("cart.html", items=products, total=total, cart_count=cart_item_count(cart))


# ---------- Checkout (now requires login) ----------

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    cart = get_cart()
    if not cart:
        return redirect(url_for("index"))

    ids = [int(pid) for pid in cart.keys()]
    products = db.get_products_by_ids(ids)
    for p in products:
        p["qty"] = cart[str(p["id"])]
        p["subtotal"] = Decimal(p["price"]) * p["qty"]
    total = sum((p["subtotal"] for p in products), Decimal("0.00"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        address = request.form.get("address", "").strip()

        if not (name and email and address):
            flash("Please fill in all fields.")
            return render_template("checkout.html", items=products, total=total,
                                    cart_count=cart_item_count(cart))

        order_items = [{"id": p["id"], "qty": p["qty"], "price": p["price"]} for p in products]
        order_id = db.create_order(name, email, address, total, order_items, user_id=session["user_id"])

        sqs_utils.send_order_message(order_id, total, email)

        save_cart({})
        return redirect(url_for("order_success", order_id=order_id))

    return render_template("checkout.html", items=products, total=total, cart_count=cart_item_count(cart))


@app.route("/order/<int:order_id>")
def order_success(order_id):
    order = db.get_order(order_id)
    if not order:
        return render_template("404.html"), 404
    return render_template("order_success.html", order=order)


# ---------- My orders (logged-in user) ----------

@app.route("/my-orders")
@login_required
def my_orders():
    orders = db.get_orders_by_user(session["user_id"])
    return render_template("my_orders.html", orders=orders)


# ---------- Admin order dashboard ----------

@app.route("/admin/orders")
@admin_required
def admin_orders():
    orders = db.get_all_orders()
    return render_template("admin_orders.html", orders=orders)


@app.route("/admin/orders/<int:order_id>/approve", methods=["POST"])
@admin_required
def approve_order(order_id):
    db.update_order_status(order_id, "SHIPPED")
    flash(f"Order #{order_id} approved and marked shipped.")
    return redirect(url_for("admin_orders"))


@app.route("/admin/orders/<int:order_id>/reject", methods=["POST"])
@admin_required
def reject_order(order_id):
    db.update_order_status(order_id, "REJECTED")
    flash(f"Order #{order_id} rejected.")
    return redirect(url_for("admin_orders"))


@app.route("/healthz")
def healthz():
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
