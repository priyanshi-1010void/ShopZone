import os
import random
from datetime import datetime, timedelta
from decimal import Decimal
from flask import (
    Flask,
    render_template,
    request,
    session,
    redirect,
    url_for,
    flash,
    jsonify,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "shopzone_super_secret_key_bca_sem3_2026")

# Database Configuration (MySQL / Cloud / SQLite Fallback)
# Can be overridden via DATABASE_URL or USE_SQLITE environment variables
DEFAULT_DB_URI = (
    "sqlite:///ecommerce.db"
    if os.environ.get("USE_SQLITE", "").lower() in ("true", "1", "yes")
    else "mysql+pymysql://root:abc123@localhost/ecommerce_db"
)
DATABASE_URI = os.environ.get("DATABASE_URL", DEFAULT_DB_URI)

# Fix postgres:// URI if provided by cloud platforms like Render or Supabase
if DATABASE_URI.startswith("postgres://"):
    DATABASE_URI = DATABASE_URI.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ==============================================================================
# MODELS
# ==============================================================================

class Role(db.Model):
    __tablename__ = "roles"
    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))


class User(db.Model):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.role_id"), nullable=False, default=2)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(15))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    role = db.relationship("Role", backref="users", lazy=True)
    addresses = db.relationship("Address", backref="user", lazy=True, cascade="all, delete-orphan")
    orders = db.relationship("Order", backref="user", lazy=True)
    reviews = db.relationship("Review", backref="user", lazy=True)


class Category(db.Model):
    __tablename__ = "categories"
    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))


class Product(db.Model):
    __tablename__ = "products"
    product_id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.category_id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    category = db.relationship("Category", backref="products", lazy=True)
    reviews = db.relationship("Review", backref="product", lazy=True, cascade="all, delete-orphan")

    @property
    def original_price(self):
        """MRP price for Flipkart/Amazon/Meesho style discount display"""
        return round(float(self.price) * 1.35, 2)

    @property
    def discount_percent(self):
        """Discount percentage"""
        return 26

    @property
    def avg_rating(self):
        if not self.reviews:
            return 4.4
        return round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)

    @property
    def review_count(self):
        return len(self.reviews) if self.reviews else 18


class Cart(db.Model):
    __tablename__ = "cart"
    cart_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("CartItem", backref="cart", lazy=True, cascade="all, delete-orphan")


class CartItem(db.Model):
    __tablename__ = "cart_items"
    cart_item_id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("cart.cart_id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    product = db.relationship("Product", backref="cart_items", lazy=True)


class Address(db.Model):
    __tablename__ = "addresses"
    address_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    address_line = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100))
    pincode = db.Column(db.String(10), nullable=False)
    country = db.Column(db.String(100), default="India")


class Order(db.Model):
    __tablename__ = "orders"
    order_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    address_id = db.Column(db.Integer, db.ForeignKey("addresses.address_id"), nullable=True)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(30), nullable=False, default="Placed")  # Placed, Processing, Shipped, Out for Delivery, Delivered, Cancelled

    address = db.relationship("Address", backref="orders", lazy=True)
    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")
    payments = db.relationship("Payment", backref="order", lazy=True, cascade="all, delete-orphan")

    @property
    def progress_step(self):
        steps = {
            "Placed": 1,
            "Processing": 2,
            "Shipped": 3,
            "Out for Delivery": 4,
            "Delivered": 5,
            "Cancelled": 0,
        }
        return steps.get(self.status, 1)


class OrderItem(db.Model):
    __tablename__ = "order_items"
    order_item_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.order_id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price = db.Column(db.Numeric(10, 2), nullable=False)

    product = db.relationship("Product", backref="order_items", lazy=True)


class Payment(db.Model):
    __tablename__ = "payments"
    payment_id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.order_id"), nullable=False)
    transaction_id = db.Column(db.String(100), unique=True)
    payment_method = db.Column(db.String(50), nullable=False)  # COD, UPI, Card, NetBanking
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_status = db.Column(db.String(30), default="Completed")  # Completed, Pending, Failed
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)


class Review(db.Model):
    __tablename__ = "reviews"
    review_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.product_id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False, default=5)
    comment = db.Column(db.Text)
    review_date = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = "notifications"
    notification_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==============================================================================
# CONTEXT PROCESSORS (Global Variables for Templates)
# ==============================================================================

@app.context_processor
def inject_global_data():
    cart_count = 0
    compare_count = len(session.get("compare_list", []))
    if "user_id" in session:
        user_cart = Cart.query.filter_by(user_id=session["user_id"]).first()
        if user_cart:
            cart_count = sum(item.quantity for item in user_cart.items)
    categories = Category.query.all()
    return {
        "cart_count": cart_count,
        "compare_count": compare_count,
        "global_categories": categories,
        "is_admin": session.get("role_id") == 1,
        "logged_user_name": session.get("user_name"),
        "logged_user_id": session.get("user_id"),
    }


# ==============================================================================
# DATABASE SEEDER & INITIALIZATION
# ==============================================================================

def seed_database():
    with app.app_context():
        try:
            db.create_all()

            # 1. Seed Roles
            if not Role.query.first():
                r1 = Role(role_id=1, role_name="Admin", description="System administrator")
                r2 = Role(role_id=2, role_name="Customer", description="Normal e-commerce customer")
                db.session.add_all([r1, r2])
                db.session.commit()

            # 2. Seed Default Admin & Customer Users
            admin_user = User.query.filter_by(email="admin@shop.com").first()
            if not admin_user:
                admin_user = User(
                    role_id=1,
                    name="Admin Superuser",
                    email="admin@shop.com",
                    password="admin123",
                    phone="9876543210",
                )
                db.session.add(admin_user)

            demo_user = User.query.filter_by(email="rahul@gmail.com").first()
            if not demo_user:
                demo_user = User(
                    role_id=2,
                    name="Rahul Sharma",
                    email="rahul@gmail.com",
                    password="rahul123",
                    phone="9876543211",
                )
                db.session.add(demo_user)
            db.session.commit()

            # 3. Seed Categories
            cat_data = [
                ("Electronics", "Smartphones, Laptops, Audio, Smart Watches"),
                ("Fashion", "Men & Women Clothing, Footwear, Accessories"),
                ("Home & Kitchen", "Appliances, Cookware, Home Decor"),
                ("Beauty & Health", "Skincare, Fragrances, Personal Grooming"),
                ("Books & Stationery", "Novels, Textbooks, Office Supplies"),
            ]
            for cname, cdesc in cat_data:
                if not Category.query.filter_by(category_name=cname).first():
                    db.session.add(Category(category_name=cname, description=cdesc))
            db.session.commit()

            # 4. Seed Rich Demo Products (Flipkart/Amazon/Meesho style)
            products_count = Product.query.count()
            if products_count < 8:
                elec_cat = Category.query.filter_by(category_name="Electronics").first()
                fash_cat = Category.query.filter_by(category_name="Fashion").first()
                home_cat = Category.query.filter_by(category_name="Home & Kitchen").first()
                book_cat = Category.query.filter_by(category_name="Books & Stationery").first()
                beauty_cat = Category.query.filter_by(category_name="Beauty & Health").first()

                sample_products = [
                    Product(
                        category_id=elec_cat.category_id if elec_cat else 1,
                        name="Galaxy S24 5G Smartphone (8GB RAM, 128GB)",
                        description="Dynamic AMOLED 2X display, 50MP AI triple camera, all-day battery with 45W fast charging.",
                        price=Decimal("49999.00"),
                        stock=24,
                        image="📱",
                    ),
                    Product(
                        category_id=elec_cat.category_id if elec_cat else 1,
                        name="SonicPro Wireless ANC Headphones",
                        description="Hybrid Active Noise Cancellation, 40-hour playback, ultra-soft memory foam ear cushions with deep bass.",
                        price=Decimal("2999.00"),
                        stock=45,
                        image="🎧",
                    ),
                    Product(
                        category_id=elec_cat.category_id if elec_cat else 1,
                        name="Aura Pro Smart Watch with AMOLED Display",
                        description="Bluetooth calling, 100+ sports modes, 24/7 SpO2 and Heart Rate monitoring, IP68 water resistant.",
                        price=Decimal("1899.00"),
                        stock=38,
                        image="⌚",
                    ),
                    Product(
                        category_id=fash_cat.category_id if fash_cat else 2,
                        name="Men Slim Fit Cotton Casual Shirt",
                        description="100% Breathable cotton fabric, modern spread collar, curve hem, perfect for casual & office wear.",
                        price=Decimal("799.00"),
                        stock=60,
                        image="👔",
                    ),
                    Product(
                        category_id=fash_cat.category_id if fash_cat else 2,
                        name="Women Embroidered Kurta with Pant Set",
                        description="Elegant ethnic pure rayon floral embroidery festive party wear outfit with dupatta.",
                        price=Decimal("1249.00"),
                        stock=30,
                        image="👗",
                    ),
                    Product(
                        category_id=fash_cat.category_id if fash_cat else 2,
                        name="AirSprint Pro Running Sneakers",
                        description="Ultra-lightweight mesh upper, responsive bouncy EVA cushioning, anti-skid rubber grip sole.",
                        price=Decimal("1599.00"),
                        stock=28,
                        image="👟",
                    ),
                    Product(
                        category_id=home_cat.category_id if home_cat else 3,
                        name="Stainless Steel Electric Kettle 1.8L",
                        description="Auto cut-off protection, 1500W rapid boiling, 360 degree swivel base, boil-dry safety.",
                        price=Decimal("849.00"),
                        stock=50,
                        image="🫖",
                    ),
                    Product(
                        category_id=home_cat.category_id if home_cat else 3,
                        name="Smart Touch Digital Air Fryer 4.5L",
                        description="Rapid 360 air circulation, 8 preset cooking menus, non-stick dishwasher-safe basket, 85% less oil.",
                        price=Decimal("3899.00"),
                        stock=15,
                        image="🍳",
                    ),
                    Product(
                        category_id=beauty_cat.category_id if beauty_cat else 4,
                        name="Vitamin C Radiance Face Glow Serum 30ml",
                        description="Infused with 10% pure Vitamin C, Hyaluronic Acid, and Ferulic Acid for bright and glowing even skin tone.",
                        price=Decimal("449.00"),
                        stock=75,
                        image="✨",
                    ),
                    Product(
                        category_id=book_cat.category_id if book_cat else 5,
                        name="Database Management Systems (Concepts & SQL)",
                        description="Comprehensive textbook covering ER modeling, Relational Algebra, Normalization, SQL & NoSQL architectures.",
                        price=Decimal("599.00"),
                        stock=40,
                        image="📚",
                    ),
                ]
                db.session.add_all(sample_products)
                db.session.commit()

            # 5. Seed Demo Address for User
            u = User.query.filter_by(email="rahul@gmail.com").first()
            if u and not Address.query.filter_by(user_id=u.user_id).first():
                demo_addr = Address(
                    user_id=u.user_id,
                    address_line="Flat 402, Sunshine Heights, MG Road",
                    city="Mumbai",
                    state="Maharashtra",
                    pincode="400001",
                    country="India",
                )
                db.session.add(demo_addr)
                db.session.commit()

            # 6. Seed Demo Reviews
            p1 = Product.query.first()
            if p1 and u and not Review.query.first():
                r1 = Review(
                    user_id=u.user_id,
                    product_id=p1.product_id,
                    rating=5,
                    comment="Outstanding build quality and battery life! Flipkart/Amazon level fast delivery from ShopZone. Highly recommended!",
                )
                db.session.add(r1)
                db.session.commit()

            # 7. Seed Demo Order
            if u and not Order.query.first():
                addr = Address.query.filter_by(user_id=u.user_id).first()
                sample_order = Order(
                    user_id=u.user_id,
                    address_id=addr.address_id if addr else None,
                    total_amount=Decimal("3847.00"),
                    status="Shipped",
                    order_date=datetime.utcnow() - timedelta(days=2),
                )
                db.session.add(sample_order)
                db.session.flush()

                p_items = Product.query.limit(2).all()
                for p in p_items:
                    db.session.add(
                        OrderItem(
                            order_id=sample_order.order_id,
                            product_id=p.product_id,
                            quantity=1,
                            price=p.price,
                        )
                    )
                db.session.add(
                    Payment(
                        order_id=sample_order.order_id,
                        transaction_id="TXN" + str(random.randint(100000, 999999)),
                        payment_method="UPI / QR Code",
                        amount=Decimal("3847.00"),
                        payment_status="Completed",
                    )
                )
                db.session.commit()

        except Exception as e:
            print(f"[Seed Info] Note during DB seeder: {e}")


# ==============================================================================
# PAGE 1: HOME PAGE
# ==============================================================================

@app.route("/")
def home():
    featured = Product.query.limit(8).all()
    categories = Category.query.all()
    trending = Product.query.order_by(Product.stock.asc()).limit(4).all()
    return render_template(
        "home.html",
        featured_products=featured,
        categories=categories,
        trending_products=trending,
    )


# ==============================================================================
# PAGE 2: LOGIN PAGE (CUSTOMER)
# ==============================================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(email=email).first()
        if user and user.password == password:
            session["user_id"] = user.user_id
            session["user_name"] = user.name
            session["role_id"] = user.role_id
            session["user_email"] = user.email

            flash(f"Welcome back, {user.name}!", "success")
            if user.role_id == 1:
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("home"))
        else:
            flash("Invalid email address or password. Please try again.", "danger")

    return render_template("login.html")


# ==============================================================================
# PAGE 3: REGISTER PAGE
# ==============================================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if password != confirm_password:
            flash("Passwords do not match! Please check and try again.", "danger")
            return render_template("register.html", name=name, email=email, phone=phone)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("An account with this email already exists. Please login instead.", "warning")
            return render_template("register.html", name=name, phone=phone)

        new_user = User(
            role_id=2,  # Customer
            name=name,
            email=email,
            password=password,
            phone=phone,
        )
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! You can now login with your credentials.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# ==============================================================================
# LOGOUT ROUTE
# ==============================================================================

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been successfully logged out.", "info")
    return redirect(url_for("login"))


# ==============================================================================
# PAGE 4: PRODUCT LISTING / SHOP PAGE
# ==============================================================================

@app.route("/products")
def products():
    query = Product.query
    search_q = request.args.get("search", "").strip()
    category_id = request.args.get("category", type=int)
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    in_stock = request.args.get("in_stock")
    sort_by = request.args.get("sort", "featured")

    if search_q:
        query = query.filter(
            Product.name.ilike(f"%{search_q}%") | Product.description.ilike(f"%{search_q}%")
        )
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if in_stock == "1":
        query = query.filter(Product.stock > 0)

    if sort_by == "price_low":
        query = query.order_by(Product.price.asc())
    elif sort_by == "price_high":
        query = query.order_by(Product.price.desc())
    elif sort_by == "newest":
        query = query.order_by(Product.created_at.desc())
    elif sort_by == "name":
        query = query.order_by(Product.name.asc())
    else:
        query = query.order_by(Product.product_id.asc())

    all_products = query.all()
    categories = Category.query.all()

    return render_template(
        "products.html",
        products=all_products,
        categories=categories,
        search_q=search_q,
        selected_cat=category_id,
        min_price=min_price,
        max_price=max_price,
        in_stock=in_stock,
        sort_by=sort_by,
    )


# ==============================================================================
# PAGE 5: PRODUCT DETAILS PAGE
# ==============================================================================

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = db.get_or_404(Product, product_id)
    related = Product.query.filter(
        Product.category_id == product.category_id,
        Product.product_id != product.product_id,
    ).limit(4).all()

    # Calculate star breakdown
    reviews = product.reviews
    ratings_count = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
    for r in reviews:
        if r.rating in ratings_count:
            ratings_count[r.rating] += 1

    return render_template(
        "product_detail.html",
        product=product,
        related_products=related,
        reviews=reviews,
        ratings_count=ratings_count,
    )


# ==============================================================================
# SUBMIT REVIEW
# ==============================================================================

@app.route("/review/add/<int:product_id>", methods=["POST"])
def add_review(product_id):
    if "user_id" not in session:
        flash("Please log in to submit a review.", "warning")
        return redirect(url_for("login"))

    rating = int(request.form.get("rating", 5))
    comment = request.form.get("comment", "").strip()

    review = Review(
        user_id=session["user_id"],
        product_id=product_id,
        rating=max(1, min(5, rating)),
        comment=comment,
    )
    db.session.add(review)
    db.session.commit()
    flash("Thank you! Your product review has been published.", "success")
    return redirect(url_for("product_detail", product_id=product_id))


# ==============================================================================
# PAGE 6: PRODUCT COMPARISON PAGE
# ==============================================================================

@app.route("/compare")
def compare_page():
    compare_ids = session.get("compare_list", [])
    products = Product.query.filter(Product.product_id.in_(compare_ids)).all() if compare_ids else []
    return render_template("compare.html", products=products)


@app.route("/compare/add/<int:product_id>", methods=["POST", "GET"])
def add_to_compare(product_id):
    compare_list = session.get("compare_list", [])
    if product_id not in compare_list:
        if len(compare_list) >= 4:
            flash("You can compare up to 4 products at a time.", "warning")
        else:
            compare_list.append(product_id)
            session["compare_list"] = compare_list
            flash("Product added to comparison list!", "success")
    else:
        flash("Product is already in comparison list.", "info")

    next_url = request.args.get("next") or request.referrer or url_for("compare_page")
    return redirect(next_url)


@app.route("/compare/remove/<int:product_id>", methods=["POST", "GET"])
def remove_from_compare(product_id):
    compare_list = session.get("compare_list", [])
    if product_id in compare_list:
        compare_list.remove(product_id)
        session["compare_list"] = compare_list
        flash("Product removed from comparison.", "info")
    return redirect(url_for("compare_page"))


@app.route("/compare/clear")
def clear_compare():
    session["compare_list"] = []
    flash("Comparison list cleared.", "info")
    return redirect(url_for("compare_page"))


# ==============================================================================
# PAGE 7: CART PAGE
# ==============================================================================

@app.route("/cart")
def view_cart():
    if "user_id" not in session:
        flash("Please login to view your cart.", "info")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cart = Cart.query.filter_by(user_id=user_id).first()

    cart_items = []
    mrp_total = Decimal("0.00")
    subtotal = Decimal("0.00")
    discount = Decimal("0.00")

    if cart:
        cart_items = cart.items
        for item in cart_items:
            item_price = item.product.price * item.quantity
            item_mrp = Decimal(str(item.product.original_price)) * item.quantity
            subtotal += item_price
            mrp_total += item_mrp

    discount = mrp_total - subtotal
    # Apply coupon if in session
    coupon_code = session.get("applied_coupon", "")
    coupon_discount = Decimal("0.00")
    if coupon_code == "SAVE10":
        coupon_discount = subtotal * Decimal("0.10")
    elif coupon_code in ["MEESHO50", "FLIPKART50"]:
        coupon_discount = min(subtotal * Decimal("0.15"), Decimal("500.00"))
    elif coupon_code == "SHOPZONE20":
        coupon_discount = subtotal * Decimal("0.20")

    delivery_fee = Decimal("0.00") if subtotal > Decimal("499.00") or subtotal == Decimal("0.00") else Decimal("49.00")
    tax = (subtotal - coupon_discount) * Decimal("0.05")  # 5% GST
    grand_total = max(Decimal("0.00"), (subtotal - coupon_discount) + delivery_fee + tax)

    return render_template(
        "cart.html",
        cart_items=cart_items,
        mrp_total=mrp_total,
        subtotal=subtotal,
        discount=discount,
        coupon_code=coupon_code,
        coupon_discount=coupon_discount,
        delivery_fee=delivery_fee,
        tax=tax,
        grand_total=grand_total,
    )


@app.route("/add-to-cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):
    if "user_id" not in session:
        flash("Please log in to add items to your cart.", "warning")
        return redirect(url_for("login"))

    product = db.get_or_404(Product, product_id)
    if product.stock <= 0:
        flash("Sorry, this item is currently out of stock.", "danger")
        return redirect(url_for("product_detail", product_id=product_id))

    user_id = session["user_id"]
    quantity = int(request.form.get("quantity", 1))
    quantity = max(1, min(quantity, product.stock))

    cart = Cart.query.filter_by(user_id=user_id).first()
    if not cart:
        cart = Cart(user_id=user_id)
        db.session.add(cart)
        db.session.flush()

    existing_item = CartItem.query.filter_by(cart_id=cart.cart_id, product_id=product_id).first()
    if existing_item:
        existing_item.quantity = min(existing_item.quantity + quantity, product.stock)
    else:
        new_item = CartItem(cart_id=cart.cart_id, product_id=product_id, quantity=quantity)
        db.session.add(new_item)

    db.session.commit()
    flash(f"'{product.name}' added to your cart!", "success")

    if request.form.get("buy_now") == "1":
        return redirect(url_for("checkout"))
    return redirect(request.referrer or url_for("view_cart"))


@app.route("/update-cart/<int:item_id>", methods=["POST"])
def update_cart(item_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    item = db.get_or_404(CartItem, item_id)
    quantity = int(request.form.get("quantity", 1))

    if quantity < 1:
        quantity = 1
    if quantity > item.product.stock:
        quantity = item.product.stock

    item.quantity = quantity
    db.session.commit()
    flash("Cart quantity updated.", "success")
    return redirect(url_for("view_cart"))


@app.route("/remove-from-cart/<int:item_id>", methods=["POST"])
def remove_from_cart(item_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    item = db.get_or_404(CartItem, item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Item removed from cart.", "info")
    return redirect(url_for("view_cart"))


@app.route("/apply-coupon", methods=["POST"])
def apply_coupon():
    coupon = request.form.get("coupon_code", "").strip().upper()
    valid_coupons = ["SAVE10", "MEESHO50", "FLIPKART50", "SHOPZONE20"]

    if coupon in valid_coupons:
        session["applied_coupon"] = coupon
        flash(f"Coupon '{coupon}' applied successfully!", "success")
    elif coupon == "":
        session.pop("applied_coupon", None)
        flash("Coupon removed.", "info")
    else:
        flash("Invalid coupon code. Try SAVE10, MEESHO50, or SHOPZONE20", "danger")

    return redirect(url_for("view_cart"))


# ==============================================================================
# PAGE 8: CHECKOUT PAGE
# ==============================================================================

@app.route("/checkout")
def checkout():
    if "user_id" not in session:
        flash("Please log in to proceed to checkout.", "warning")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    user = db.session.get(User, user_id)
    cart = Cart.query.filter_by(user_id=user_id).first()

    if not cart or not cart.items:
        flash("Your cart is empty. Please add items before checking out.", "warning")
        return redirect(url_for("products"))

    addresses = Address.query.filter_by(user_id=user_id).all()

    subtotal = sum(item.product.price * item.quantity for item in cart.items)
    coupon_code = session.get("applied_coupon", "")
    coupon_discount = Decimal("0.00")
    if coupon_code == "SAVE10":
        coupon_discount = subtotal * Decimal("0.10")
    elif coupon_code in ["MEESHO50", "FLIPKART50"]:
        coupon_discount = min(subtotal * Decimal("0.15"), Decimal("500.00"))
    elif coupon_code == "SHOPZONE20":
        coupon_discount = subtotal * Decimal("0.20")

    delivery_fee = Decimal("0.00") if subtotal > Decimal("499.00") else Decimal("49.00")
    tax = (subtotal - coupon_discount) * Decimal("0.05")
    grand_total = (subtotal - coupon_discount) + delivery_fee + tax

    return render_template(
        "checkout.html",
        user=user,
        cart_items=cart.items,
        addresses=addresses,
        subtotal=subtotal,
        coupon_discount=coupon_discount,
        delivery_fee=delivery_fee,
        tax=tax,
        grand_total=grand_total,
    )


@app.route("/place-order", methods=["POST"])
def place_order():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    cart = Cart.query.filter_by(user_id=user_id).first()

    if not cart or not cart.items:
        flash("Cart is empty!", "danger")
        return redirect(url_for("products"))

    # Determine Address
    selected_address_id = request.form.get("address_id")
    if selected_address_id == "new" or not selected_address_id:
        addr_line = request.form.get("address_line", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        pincode = request.form.get("pincode", "").strip()

        if not (addr_line and city and pincode):
            flash("Please provide complete delivery address details.", "danger")
            return redirect(url_for("checkout"))

        new_addr = Address(
            user_id=user_id,
            address_line=addr_line,
            city=city,
            state=state,
            pincode=pincode,
        )
        db.session.add(new_addr)
        db.session.flush()
        address_id = new_addr.address_id
    else:
        address_id = int(selected_address_id)

    # Calculate Total
    subtotal = sum(item.product.price * item.quantity for item in cart.items)
    coupon_code = session.get("applied_coupon", "")
    coupon_discount = Decimal("0.00")
    if coupon_code == "SAVE10":
        coupon_discount = subtotal * Decimal("0.10")
    elif coupon_code in ["MEESHO50", "FLIPKART50"]:
        coupon_discount = min(subtotal * Decimal("0.15"), Decimal("500.00"))
    elif coupon_code == "SHOPZONE20":
        coupon_discount = subtotal * Decimal("0.20")

    delivery_fee = Decimal("0.00") if subtotal > Decimal("499.00") else Decimal("49.00")
    tax = (subtotal - coupon_discount) * Decimal("0.05")
    grand_total = (subtotal - coupon_discount) + delivery_fee + tax

    # Create Order
    order = Order(
        user_id=user_id,
        address_id=address_id,
        total_amount=grand_total,
        status="Placed",
    )
    db.session.add(order)
    db.session.flush()

    # Move cart items to order items and decrease stock
    for item in cart.items:
        order_item = OrderItem(
            order_id=order.order_id,
            product_id=item.product_id,
            quantity=item.quantity,
            price=item.product.price,
        )
        db.session.add(order_item)
        # Update stock
        if item.product.stock >= item.quantity:
            item.product.stock -= item.quantity

    # Create Payment record
    payment_method = request.form.get("payment_method", "Cash on Delivery")
    payment = Payment(
        order_id=order.order_id,
        transaction_id="TXN" + str(random.randint(10000000, 99999999)),
        payment_method=payment_method,
        amount=grand_total,
        payment_status="Completed" if payment_method != "Cash on Delivery" else "Pending (COD)",
    )
    db.session.add(payment)

    # Clear Cart & Coupon
    CartItem.query.filter_by(cart_id=cart.cart_id).delete()
    session.pop("applied_coupon", None)

    # Add Confirmation Notification
    notif = Notification(
        user_id=user_id,
        title=f"Order #{order.order_id} Confirmed! 🎉",
        message=f"Thank you for ordering with ShopZone. Your package is being packed and prepared for dispatch.",
    )
    db.session.add(notif)
    db.session.commit()

    flash("Order placed successfully! 🎉", "success")
    return redirect(url_for("order_confirmation", order_id=order.order_id))


# ==============================================================================
# PAGE 9: ORDER CONFIRMATION PAGE
# ==============================================================================

@app.route("/order-success/<int:order_id>")
def order_confirmation(order_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    order = db.get_or_404(Order, order_id)
    if order.user_id != session["user_id"] and session.get("role_id") != 1:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("home"))

    est_delivery = order.order_date + timedelta(days=3)
    payment = Payment.query.filter_by(order_id=order.order_id).first()

    return render_template(
        "order_success.html",
        order=order,
        est_delivery=est_delivery,
        payment=payment,
    )


# ==============================================================================
# PAGE 10: MY ORDERS PAGE
# ==============================================================================

@app.route("/my-orders")
def my_orders():
    if "user_id" not in session:
        flash("Please log in to view your orders.", "info")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    status_filter = request.args.get("status", "all")

    query = Order.query.filter_by(user_id=user_id)
    if status_filter != "all":
        query = query.filter_by(status=status_filter)

    orders = query.order_by(Order.order_date.desc()).all()

    return render_template(
        "my_orders.html",
        orders=orders,
        status_filter=status_filter,
    )


# ==============================================================================
# PAGE 11: ORDER DETAILS / TRACKING PAGE
# ==============================================================================

@app.route("/order/<int:order_id>")
def order_tracking(order_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    order = db.get_or_404(Order, order_id)
    if order.user_id != session["user_id"] and session.get("role_id") != 1:
        flash("Unauthorized access.", "danger")
        return redirect(url_for("home"))

    payment = Payment.query.filter_by(order_id=order.order_id).first()
    est_delivery = order.order_date + timedelta(days=3)

    return render_template(
        "order_tracking.html",
        order=order,
        payment=payment,
        est_delivery=est_delivery,
    )


@app.route("/order/<int:order_id>/cancel", methods=["POST"])
def cancel_order(order_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    order = db.get_or_404(Order, order_id)
    if order.user_id != session["user_id"] and session.get("role_id") != 1:
        flash("Unauthorized.", "danger")
        return redirect(url_for("home"))

    if order.status in ["Placed", "Processing"]:
        order.status = "Cancelled"
        # Restock products
        for item in order.items:
            item.product.stock += item.quantity
        db.session.commit()
        flash("Order has been cancelled successfully. Refund will be processed in 24 hours.", "info")
    else:
        flash("Order cannot be cancelled as it has already been shipped.", "warning")

    return redirect(url_for("order_tracking", order_id=order_id))


@app.route("/order/<int:order_id>/return", methods=["POST"])
def return_order(order_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    order = db.get_or_404(Order, order_id)
    reason = request.form.get("reason", "Not satisfied")
    flash(f"Return request initiated for Order #{order.order_id}. Reason: {reason}. Pickup will be arranged in 48 hours.", "success")
    return redirect(url_for("order_tracking", order_id=order_id))


# ==============================================================================
# PAGE 12: PROFILE / ACCOUNT PAGE
# ==============================================================================

@app.route("/profile")
def profile():
    if "user_id" not in session:
        flash("Please login to view your profile.", "info")
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    addresses = Address.query.filter_by(user_id=user.user_id).all()
    order_count = Order.query.filter_by(user_id=user.user_id).count()
    review_count = Review.query.filter_by(user_id=user.user_id).count()

    return render_template(
        "profile.html",
        user=user,
        addresses=addresses,
        order_count=order_count,
        review_count=review_count,
    )


@app.route("/profile/update", methods=["POST"])
def update_profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = db.session.get(User, session["user_id"])
    user.name = request.form.get("name", user.name).strip()
    user.phone = request.form.get("phone", user.phone).strip()

    new_pw = request.form.get("new_password", "").strip()
    if new_pw:
        user.password = new_pw

    db.session.commit()
    session["user_name"] = user.name
    flash("Profile updated successfully!", "success")
    return redirect(url_for("profile"))


@app.route("/address/add", methods=["POST"])
def add_address():
    if "user_id" not in session:
        return redirect(url_for("login"))

    new_addr = Address(
        user_id=session["user_id"],
        address_line=request.form.get("address_line", "").strip(),
        city=request.form.get("city", "").strip(),
        state=request.form.get("state", "").strip(),
        pincode=request.form.get("pincode", "").strip(),
    )
    db.session.add(new_addr)
    db.session.commit()
    flash("New delivery address added.", "success")
    return redirect(request.referrer or url_for("profile"))


@app.route("/address/delete/<int:address_id>", methods=["POST"])
def delete_address(address_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    addr = db.get_or_404(Address, address_id)
    if addr.user_id == session["user_id"] or session.get("role_id") == 1:
        db.session.delete(addr)
        db.session.commit()
        flash("Address deleted.", "info")
    return redirect(url_for("profile"))


# ==============================================================================
# PAGE 13: ADMIN LOGIN PAGE
# ==============================================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(email=email).first()
        if user and user.password == password and user.role_id == 1:
            session["user_id"] = user.user_id
            session["user_name"] = user.name
            session["role_id"] = 1
            session["user_email"] = user.email
            flash(f"Welcome to Admin Command Center, {user.name}!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid administrator credentials.", "danger")

    return render_template("admin/login.html")


# ==============================================================================
# PAGE 14: ADMIN DASHBOARD
# ==============================================================================

@app.route("/admin/dashboard")
def admin_dashboard():
    if session.get("role_id") != 1:
        flash("Admin privileges required.", "warning")
        return redirect(url_for("admin_login"))

    total_revenue = db.session.query(func.sum(Order.total_amount)).filter(Order.status != "Cancelled").scalar() or 0
    total_orders = Order.query.count()
    total_products = Product.query.count()
    total_customers = User.query.filter_by(role_id=2).count()

    recent_orders = Order.query.order_by(Order.order_date.desc()).limit(6).all()
    low_stock_products = Product.query.filter(Product.stock <= 10).all()
    recent_users = User.query.filter_by(role_id=2).order_by(User.user_id.desc()).limit(5).all()

    return render_template(
        "admin/dashboard.html",
        total_revenue=total_revenue,
        total_orders=total_orders,
        total_products=total_products,
        total_customers=total_customers,
        recent_orders=recent_orders,
        low_stock_products=low_stock_products,
        recent_users=recent_users,
    )


# ==============================================================================
# PAGE 15: PRODUCT & CATEGORY MANAGEMENT
# ==============================================================================

@app.route("/admin/products")
def admin_products():
    if session.get("role_id") != 1:
        return redirect(url_for("admin_login"))

    products = Product.query.order_by(Product.product_id.desc()).all()
    categories = Category.query.all()
    return render_template("admin/products.html", products=products, categories=categories)


@app.route("/admin/product/add", methods=["POST"])
def admin_add_product():
    if session.get("role_id") != 1:
        return redirect(url_for("admin_login"))

    name = request.form.get("name")
    category_id = int(request.form.get("category_id"))
    price = Decimal(request.form.get("price"))
    stock = int(request.form.get("stock"))
    description = request.form.get("description")
    image = request.form.get("image", "🛍️")

    product = Product(
        name=name,
        category_id=category_id,
        price=price,
        stock=stock,
        description=description,
        image=image,
    )
    db.session.add(product)
    db.session.commit()
    flash(f"Product '{name}' created successfully!", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/product/edit/<int:product_id>", methods=["POST"])
def admin_edit_product(product_id):
    if session.get("role_id") != 1:
        return redirect(url_for("admin_login"))

    product = db.get_or_404(Product, product_id)
    product.name = request.form.get("name")
    product.category_id = int(request.form.get("category_id"))
    product.price = Decimal(request.form.get("price"))
    product.stock = int(request.form.get("stock"))
    product.description = request.form.get("description")
    product.image = request.form.get("image", product.image)

    db.session.commit()
    flash(f"Product '{product.name}' updated successfully!", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/product/delete/<int:product_id>", methods=["POST"])
def admin_delete_product(product_id):
    if session.get("role_id") != 1:
        return redirect(url_for("admin_login"))

    product = db.get_or_404(Product, product_id)
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted successfully.", "info")
    return redirect(url_for("admin_products"))


@app.route("/admin/category/add", methods=["POST"])
def admin_add_category():
    if session.get("role_id") != 1:
        return redirect(url_for("admin_login"))

    cname = request.form.get("category_name", "").strip()
    cdesc = request.form.get("description", "").strip()

    if cname:
        new_cat = Category(category_name=cname, description=cdesc)
        db.session.add(new_cat)
        db.session.commit()
        flash(f"Category '{cname}' created.", "success")
    return redirect(url_for("admin_products"))


@app.route("/admin/category/delete/<int:category_id>", methods=["POST"])
def admin_delete_category(category_id):
    if session.get("role_id") != 1:
        return redirect(url_for("admin_login"))

    cat = db.get_or_404(Category, category_id)
    if cat.products:
        flash(f"Cannot delete category '{cat.category_name}' because it contains {len(cat.products)} products.", "danger")
    else:
        db.session.delete(cat)
        db.session.commit()
        flash(f"Category deleted.", "info")
    return redirect(url_for("admin_products"))


# ==============================================================================
# PAGE 16: ORDER MANAGEMENT
# ==============================================================================

@app.route("/admin/orders")
def admin_orders():
    if session.get("role_id") != 1:
        return redirect(url_for("admin_login"))

    status = request.args.get("status")
    query = Order.query.order_by(Order.order_date.desc())
    if status:
        query = query.filter_by(status=status)

    orders = query.all()
    return render_template("admin/orders.html", orders=orders, current_status=status)


@app.route("/admin/order/<int:order_id>/update-status", methods=["POST"])
def admin_update_order_status(order_id):
    if session.get("role_id") != 1:
        return redirect(url_for("admin_login"))

    order = db.get_or_404(Order, order_id)
    new_status = request.form.get("status")
    if new_status:
        order.status = new_status
        db.session.commit()
        flash(f"Order #{order.order_id} status changed to {new_status}.", "success")

    return redirect(url_for("admin_orders"))


# ==============================================================================
# PAGE 17: USERS, REVIEWS & RETURNS MANAGEMENT
# ==============================================================================

@app.route("/admin/users-reviews")
def admin_users_reviews():
    if session.get("role_id") != 1:
        return redirect(url_for("admin_login"))

    users = User.query.order_by(User.user_id.desc()).all()
    reviews = Review.query.order_by(Review.review_date.desc()).all()
    cancelled_orders = Order.query.filter_by(status="Cancelled").all()

    return render_template(
        "admin/users_reviews.html",
        users=users,
        reviews=reviews,
        cancelled_orders=cancelled_orders,
    )


@app.route("/admin/review/delete/<int:review_id>", methods=["POST"])
def admin_delete_review(review_id):
    if session.get("role_id") != 1:
        return redirect(url_for("admin_login"))

    review = db.get_or_404(Review, review_id)
    db.session.delete(review)
    db.session.commit()
    flash("Review removed by moderator.", "info")
    return redirect(url_for("admin_users_reviews"))


# ==============================================================================
# PAGE 18: REPORTS & ANALYTICS
# ==============================================================================

@app.route("/admin/reports")
def admin_reports():
    if session.get("role_id") != 1:
        return redirect(url_for("admin_login"))

    # Sales by category
    categories = Category.query.all()
    cat_sales = []
    for cat in categories:
        cat_total = Decimal("0.00")
        for p in cat.products:
            for oi in p.order_items:
                if oi.order.status != "Cancelled":
                    cat_total += oi.price * oi.quantity
        cat_sales.append({"name": cat.category_name, "total": cat_total, "count": len(cat.products)})

    # Top selling products
    top_products = Product.query.all()
    top_products_data = []
    for p in top_products:
        sold_qty = sum(oi.quantity for oi in p.order_items if oi.order.status != "Cancelled")
        revenue = sum(oi.price * oi.quantity for oi in p.order_items if oi.order.status != "Cancelled")
        top_products_data.append({"product": p, "qty": sold_qty, "revenue": revenue})
    top_products_data.sort(key=lambda x: x["qty"], reverse=True)

    # Total metrics
    total_sales = sum(cs["total"] for cs in cat_sales) or Decimal("12499.00")
    total_orders_count = Order.query.count()

    return render_template(
        "admin/reports.html",
        cat_sales=cat_sales,
        top_products_data=top_products_data[:6],
        total_sales=total_sales,
        total_orders_count=total_orders_count,
    )



# ==============================================================================
# MAIN ENTRYPOINT & AUTO-SEED
# ==============================================================================

# Ensure tables & seed data are initialized
try:
    seed_database()
except Exception as _seed_err:
    print(f"[DB Init Note] {_seed_err}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug)