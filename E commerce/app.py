from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from flask_bcrypt import Bcrypt
from decimal import Decimal

app = Flask(__name__)
app.secret_key = 'your_secret_key'
bcrypt = Bcrypt(app)

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",  # default XAMPP MySQL password is empty
    database="ecommerce_db"
)

# Home page: show products
@app.route('/')
def home():
    search = request.args.get('search', '').strip()
    selected_category = request.args.get('category', '')
    cursor = db.cursor(dictionary=True)
    # Get all unique categories for the dropdown
    cursor.execute("SELECT DISTINCT category FROM products")
    categories = [row['category'] for row in cursor.fetchall()]
    # Build query for products
    query = "SELECT * FROM products WHERE 1"
    params = []
    if search:
        query += " AND (name LIKE %s OR description LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    if selected_category and selected_category != 'All':
        query += " AND category = %s"
        params.append(selected_category)
    print('DEBUG:', query, params)  # Debug print
    cursor.execute(query, params)
    products = cursor.fetchall()
    return render_template('home.html', products=products, categories=categories, selected_category=selected_category, search=search)

# User registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
        cursor = db.cursor()
        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, password))
            db.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash('Error: ' + str(err))
    return render_template('register.html')

# User login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

# User logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# Add to cart
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    quantity = int(request.form.get('quantity', 1))
    cart = session.get('cart', {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + quantity
    session['cart'] = cart
    flash('Product added to cart!')
    return redirect(url_for('home'))

# View cart
@app.route('/cart')
def cart():
    cart = session.get('cart', {})
    products = []
    total = Decimal('0.00')
    if cart:
        cursor = db.cursor(dictionary=True)
        product_ids = tuple(map(int, cart.keys()))
        format_strings = ','.join(['%s'] * len(product_ids))
        cursor.execute(f"SELECT * FROM products WHERE id IN ({format_strings})", product_ids)
        db_products = cursor.fetchall()
        for product in db_products:
            pid = str(product['id'])
            product['quantity'] = cart[pid]
            product['subtotal'] = Decimal(product['price']) * product['quantity']
            total += product['subtotal']
            products.append(product)
    return render_template('cart.html', products=products, total=total)

# Remove from cart
@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    cart = session.get('cart', {})
    cart.pop(str(product_id), None)
    session['cart'] = cart
    flash('Product removed from cart.')
    return redirect(url_for('cart'))

# Place order
@app.route('/checkout', methods=['POST'])
def checkout():
    if 'user_id' not in session:
        flash('Please log in to place an order.')
        return redirect(url_for('login'))
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty.')
        return redirect(url_for('home'))
    cursor = db.cursor(dictionary=True)
    product_ids = tuple(map(int, cart.keys()))
    format_strings = ','.join(['%s'] * len(product_ids))
    cursor.execute(f"SELECT * FROM products WHERE id IN ({format_strings})", product_ids)
    db_products = cursor.fetchall()
    total = Decimal('0.00')
    for product in db_products:
        pid = str(product['id'])
        total += Decimal(product['price']) * cart[pid]
    # Insert order
    cursor2 = db.cursor()
    cursor2.execute("INSERT INTO orders (user_id, total) VALUES (%s, %s)", (session['user_id'], total))
    order_id = cursor2.lastrowid
    # Insert order items
    for product in db_products:
        pid = str(product['id'])
        cursor2.execute(
            "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (%s, %s, %s, %s)",
            (order_id, product['id'], cart[pid], product['price'])
        )
    db.commit()
    session['cart'] = {}
    flash('Order placed successfully!')
    return render_template('order_success.html', order_id=order_id)

if __name__ == '__main__':
    app.run(debug=True) 