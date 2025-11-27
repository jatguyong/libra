import os
import datetime


from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    portfolio = db.execute("SELECT * FROM portfolios WHERE user_id = ?", session["user_id"])
    grand_total = 0
    new_portfolio = []
    for item in portfolio:
        price = lookup(item["stock"])
        if not price:
            return apology("error looking up occurred", 403)

        price = price["price"]
        shares = item["shares"]
        grand_total += price * shares

        data = {
            "symbol": item["stock"],
            "shares": int(shares),
            "price": float(price),
            "total": float(price) * float(shares)
        }
        new_portfolio.append(data)

    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    grand_total += cash

    return render_template("index.html", grand_total=grand_total, portfolio=new_portfolio, cash=cash)

    return apology("TODO")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "POST":
        stock = request.form.get("symbol")
        shares = request.form.get("shares")

        if stock is None:
            return apology("must provide stock", 400)

        try:
            shares = int(shares)
        except ValueError:
            return apology("invalid number of shares", 400)
        
        if shares is None or int(shares) < 0:
            return apology("invalid number of shares", 400)

        quotation = lookup(stock)

        if quotation is None:
            return apology("stock does not exist", 400)

        price = float(quotation["price"])

        user_cash = float(db.execute("SELECT cash FROM users WHERE id = ?",
                          session["user_id"])[0]["cash"])

        if price * shares > user_cash:
            return apology("insufficient cash balance", 400)

        cash_balance = user_cash - price * shares

        datetimenow = str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        stock_id_in_portfolio = db.execute(
            "SELECT id FROM portfolios WHERE user_id = ? AND stock = ?", session["user_id"], stock)
        if stock_id_in_portfolio:
            stock_id_in_portfolio = stock_id_in_portfolio[0]["id"]
            old_shares = float(db.execute(
                "SELECT shares FROM portfolios WHERE id = ?", stock_id_in_portfolio)[0]["shares"])
            new_shares = old_shares + shares
            db.execute("UPDATE portfolios SET shares = ? WHERE id = ?",
                       new_shares, stock_id_in_portfolio)
        else:
            db.execute("INSERT INTO portfolios (user_id, stock, shares) VALUES (?, ?, ?)",
                       session["user_id"], stock, shares)

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_balance, session["user_id"])
        db.execute("INSERT INTO transactions (user_id, stock, type, shares, price, datetime) VALUES (?, ?, ?, ?, ?, ?)",
                   session["user_id"], stock, "buy", shares, price, datetimenow)
        return redirect("/")

    else:
        return render_template("buy.html")
    return apology("TODO")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ?", session["user_id"])
    return render_template("history.html", transactions=transactions)
    return apology("TODO")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        symbol = request.form.get("symbol")
        if symbol is None:
            return apology("symbol empty", 400)

        quotation = lookup(symbol)

        if quotation is None:
            return apology("stock does not exist", 400)

        return render_template("quoted.html", quotation=quotation)
    else:
        return render_template("quote.html")
    return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if username is None or username == "":
            return apology("must provide username", 400)
        elif password is None or password == "":
            return apology("must provide password", 400)
        elif confirmation is None or confirmation == "":
            return apology("must provide password confirmation", 400)
        elif password != confirmation:
            return apology("password and confirmation do not match", 400)

        user_dne = len(db.execute("SELECT id FROM users WHERE username = ?", username)) == 0

        if user_dne:
            new_id = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                                username, generate_password_hash(password))
            session["user_id"] = new_id
            return render_template("login.html")
        else:
            return apology("username already taken", 400)
    else:
        return render_template("register.html")
    return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        stock = request.form.get("symbol")
        if stock == "Symbol":
            return apology("must provide stock to sell", 400)

        shares = request.form.get("shares")

        if not shares.isnumeric():
            return apology("invalid number of shares", 400)

        if int(shares) < 1:
            return apology("invalid number of shares", 400)

        shares = int(shares)

        shares_remaining = int(db.execute(
            "SELECT shares FROM portfolios WHERE user_id = ? AND stock = ?", session["user_id"], stock)[0]["shares"])
        if shares > shares_remaining:
            return apology("invalid number of shares", 400)

        new_shares = shares_remaining - shares
        price = lookup(stock)
        if not price:
            return apology("lookup error occurred while selling", 400)

        price = price["price"]
        cash = float(db.execute("SELECT cash FROM users WHERE id = ?",
                     session["user_id"])[0]["cash"])
        new_cash = cash + price * shares
        datetimenow = str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])
        db.execute("UPDATE portfolios SET shares = ? WHERE user_id = ? AND stock = ?",
                   new_shares, session["user_id"], stock)
        db.execute("INSERT INTO transactions (user_id, stock, type, shares, price, datetime) VALUES (?, ?, ?, ?, ?, ?)",
                   session["user_id"], stock, "sell", shares, price, datetimenow)

        return redirect("/")

    else:
        stocks = db.execute("SELECT stock FROM portfolios WHERE user_id = ?", session["user_id"])
        return render_template("sell.html", stocks=stocks)
    return apology("TODO")
