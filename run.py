from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os
import threading
import webview
import pywhatkit as kit

app = Flask(__name__)

# Secret key for session management
app.secret_key = os.urandom(24)

# Configuration for SQLite Database
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///customer_db.sqlite'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://DB_USER:DB_PASS@mysql-1f761a7d-prasadcpatil246-f8f0.b.aivencloud.com:14627/ledgerdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Redirect unauthorized users to the login page
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"


# User model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    customers = db.relationship('Customer', backref='user', lazy=True)


# Other models
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'credit' or 'debit'
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    remark = db.Column(db.String(255), nullable=True)


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(15), nullable=False)
    amount = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transactions = db.relationship('Transaction', cascade="all, delete-orphan", backref='customer')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_click_to_chat_url(customer_name, customer_mobile, reminder_details, amount, user):
    """
    Generates a WhatsApp Click-to-Chat URL with a pre-filled reminder message.
    """
    # Prepare the message text
    message_body = (
        f"Dear {customer_name},\n\n"
        f"You have the following unpaid bills:\n{reminder_details}\n\n"
        f"Total Amount Due: {amount}\n\n"
        f"Please make the payment at your earliest convenience.\n\n"
        f"Regards,\n"
        f"{user} \n "
        f"Powered By Ledger"
    )
    
    # Encode the message for the URL
    import urllib.parse
    encoded_message = urllib.parse.quote(message_body)  # Properly encode the message for a URL
    
    # Generate the WhatsApp Click-to-Chat URL
    whatsapp_url = f"https://wa.me/{customer_mobile}?text={encoded_message}"
    return whatsapp_url


# Function to send WhatsApp reminders whatapp web
# def send_whatsapp_reminder(customer_name, customer_mobile, reminder_details, amount):
#     message_body = f"Dear {customer_name},\n\nYou have the following unpaid bills:\n{reminder_details}\n\nTotal Amount Due: {amount}\n\nPlease make the payment at your earliest convenience.\n\nRegards,\nYour Store Name Powered By Ledger"
#     try:
#         kit.sendwhatmsg_instantly(f"+{customer_mobile}", message_body, wait_time=15)
#         return {"status": "success", "message": f"WhatsApp message sent to {customer_name}."}
#     except Exception as e:
#         return {"status": "error", "message": f"Failed to send message: {str(e)}"}


# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            flash("Login successful!", "success")
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash("Invalid username or password. Please try again.", "danger")

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if User.query.filter_by(username=username).first():
            flash("Username already exists. Please choose a different username.", "danger")
        else:
            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for('login'))

    return render_template('setup.html')


@app.route('/')
@login_required
def index():
    user = current_user
    username = user.username if user else 'Guest'
    page = request.args.get('page', 1, type=int)
    customers = Customer.query.filter_by(user_id=user.id).paginate(page=page, per_page=7, error_out=False)
    total_amount = db.session.query(db.func.sum(Customer.amount)).filter_by(user_id=user.id).scalar() or 0

    return render_template('index.html', customers=customers.items, total_amount=total_amount, username=username, pagination=customers)


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    if request.method == 'POST':
        name = request.form['name']
        mobile = request.form['mobile']
        amount = request.form['amount']

        new_customer = Customer(name=name, mobile=mobile, amount=amount, user_id=current_user.id)
        db.session.add(new_customer)
        db.session.commit()

        return redirect(url_for('index'))
    return render_template('add_customer.html')


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_customer(id):
    customer = Customer.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        customer.name = request.form['name']
        customer.mobile = request.form['mobile']
        customer.amount = request.form['amount']
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('edit_customer.html', customer=customer)


@app.route('/delete/<int:id>')
@login_required
def delete_customer(id):
    customer = Customer.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    db.session.delete(customer)
    db.session.commit()
    return redirect(url_for('index'))


@app.route('/transaction/<int:id>', methods=['POST'])
@login_required
def transaction(id):
    customer = Customer.query.get_or_404(id)
    amount = float(request.form['amount'])
    remark = request.form['remark']
    action = request.form['action']  # Get the action (credit or debit) from the clicked button

    if action == 'credit':
        customer.amount += amount
        transaction = Transaction(customer_id=id, type='credit', amount=amount, remark=remark)

    elif action == 'debit':
        if customer.amount >= amount:
            customer.amount -= amount
            transaction = Transaction(customer_id=id, type='debit', amount=amount, remark=remark)
        else:
            error_message = "Insufficient balance. Please check your account and try again."
            return render_template('error.html', error_message=error_message), 400

    db.session.add(transaction)
    db.session.commit()

    return redirect(url_for('index'))

#whatsapp web
# @app.route('/send_reminder/<int:customer_id>', methods=['GET'])
# @login_required
# def send_reminder(customer_id):
#     customer = Customer.query.get_or_404(customer_id)
#     reminder_details = f"Unpaid bills for {customer.name}"
#     amount = customer.amount
#
#     result = send_whatsapp_reminder(customer.name, customer.mobile, reminder_details, amount)
#
#     if result["status"] == "success":
#         flash(result["message"], "success")
#     else:
#         flash(result["message"], "error")
#
#     return redirect(url_for('index'))

@app.route('/send_reminder/<int:customer_id>', methods=['GET'])
@login_required
def send_reminder(customer_id):
    """
    Generates a WhatsApp Click-to-Chat URL for a customer with unpaid bills.
    Redirects the user to WhatsApp Web or Mobile with the pre-filled message.
    """
    # Get the customer details from the database
    customer = Customer.query.get_or_404(customer_id)

    # Use flask-login's `current_user` to get the logged-in user's username
    user = current_user.username

    reminder_details = f"Unpaid bills for {customer.name}"  # Customize this as needed
    amount = customer.amount  # Fetch customer's total due amount

    # Generate the WhatsApp Click-to-Chat URL
    whatsapp_url = generate_click_to_chat_url(customer.name, customer.mobile, reminder_details, amount, user)

    # Redirect the user to the WhatsApp Click-to-Chat URL
    return redirect(whatsapp_url)


@app.route('/print_invoice/<int:id>')
@login_required
def print_invoice(id):
    customer = Customer.query.get_or_404(id)
    transactions = Transaction.query.filter_by(customer_id=id).order_by(Transaction.date.desc()).all()
    current_datetime = datetime.utcnow()
    return render_template('invoice.html', customer=customer, transactions=transactions, current_datetime=current_datetime)


@app.route('/print_customers')
@login_required
def print_customers():
    customers = Customer.query.filter_by(user_id=current_user.id).all()
    total_amount = sum(customer.amount for customer in customers)
    current_datetime = datetime.utcnow()
    return render_template('print.html', customers=customers, total_amount=total_amount, total_customers=len(customers), current_datetime=current_datetime)


@app.route('/search')
@login_required
def search():
    query = request.args.get('query')
    page = request.args.get('page', 1, type=int)

    if query:
        customers = Customer.query.filter(
            (Customer.name.ilike(f"%{query}%") | Customer.mobile.ilike(f"%{query}%")) & (Customer.user_id == current_user.id)
        ).paginate(page=page, per_page=7, error_out=False)

        total_amount = db.session.query(db.func.sum(Customer.amount)).filter(
            (Customer.name.ilike(f"%{query}%") | Customer.mobile.ilike(f"%{query}%")) & (Customer.user_id == current_user.id)
        ).scalar() or 0
    else:
        flash("No Matching Records Found", "info")
        customers = None
        total_amount = 0

    return render_template('index.html', customers=customers.items if customers else [], total_amount=total_amount, query=query, pagination=customers)


# Function to run Flask in a separate thread
def run_flask():
    app.run(debug=False, use_reloader=False)



if __name__ == '__main__':
    # Start Flask in the main thread
    run_flask()
