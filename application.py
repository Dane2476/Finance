from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
    stocks = db.execute("SELECT * FROM portfolio WHERE userid=:id", id=session["user_id"])

    total = 0
    for i in range(0, len(stocks)):
        total += stocks[i]["purchase"]

    total += cash[0]["cash"]

    return render_template("portfolio.html", stocks=stocks, total=total, cash=cash[0]["cash"])

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("Please specify which stock you would like to purchase")

        elif not request.form.get("shares") or not request.form.get("shares").isdigit():
            return apology("Please specify how many shares you would like to purchase")

        else:
            symbol = request.form.get("symbol")
            shares = request.form.get("shares")

            quote = lookup(symbol)
            if quote == None:
                return apology("Could not find stock", 400)
            price = quote["price"]
            purchase = (int(shares) * quote["price"])
            purchase = round(purchase, 2)

            cash = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
            if int(cash[0]["cash"]) < purchase:
                return apology("Cannot afford this purchase", 400)

            else:
                portfolio = db.execute("SELECT * FROM portfolio WHERE userid = :userid", userid=session["user_id"])
                counter = 0
                for i in portfolio:
                    if i["symbol"] == request.form.get("symbol"):
                        db.execute("UPDATE portfolio SET shares = shares + :shares, purchase = purchase + :purchase WHERE userid = :userid AND symbol = :symbol",
                            symbol=symbol,
                            shares=shares,
                            purchase=purchase,
                            userid=session["user_id"])
                        db.execute("UPDATE users SET cash = cash - :purchase WHERE id = :id", purchase=purchase, id=session["user_id"])
                        counter += 1
                if counter == 0:
                    db.execute("INSERT INTO portfolio (symbol, name, shares, price, userid, purchase) VALUES (:symbol, :name, :shares, :price, :userid, :purchase)",
                                symbol=symbol,
                                name=symbol,
                                shares=shares,
                                price=price,
                                purchase=purchase,
                                userid=session["user_id"])
                    db.execute("UPDATE users SET cash = cash - :purchase WHERE id = :id", purchase=purchase, id=session["user_id"])
                db.execute("INSERT INTO history (symbol, shares, price, userid) VALUES (:symbol, :shares, :price, :userid)",
                            symbol=symbol,
                            shares=shares,
                            price=price,
                            userid=session["user_id"])
                return redirect("/")

    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    history = db.execute("SELECT * FROM history WHERE userid = :userid", userid=session["user_id"])

    return render_template("history.html", history=history)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 400)

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

        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("Stock does not exist!", 400)

        return render_template("quoted.html", name=quote["name"], price=quote["price"], symbol=quote["symbol"])

    else:
        return render_template("quote.html" )

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":

        if not request.form.get("password"):
            return apology("Must provide password", 400)

        elif not request.form.get("confirmation"):
            return apology("Must provide password confirmation", 400)

        elif not request.form.get("username"):
            return apology("Must provide username", 400)

        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Passwords must match", 400)

        else:
            hash = generate_password_hash(request.form.get("password"))
            username = request.form.get("username")
            result = db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)", username=username, hash=hash)
            if not result:
                return apology("Username already exists", 400)

            rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
            session["user_id"] = rows[0]["id"]

            return redirect("/")

    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("Please select a stock to sell", 400)
        elif not request.form.get("shares") or not request.form.get("shares").isdigit():
            return apology("Please specify amount of shares to sell", 400)
        else:


            stock = lookup(request.form.get("symbol"))
            if not stock:
                return apology("Error, try again", 400)

            shares = int(request.form.get("shares"))
            sale = shares * stock["price"]
            symbol = request.form.get("symbol")

            cash = db.execute("SELECT cash FROM users WHERE id=:id", id=session["user_id"])
            portfolio = db.execute("SELECT * FROM portfolio WHERE userid=:id AND symbol=:symbol", id=session["user_id"], symbol=symbol)

            counter = 0

            #  if the user requests more shares then they have, return error
            for i in portfolio:
                if i["shares"] < shares:
                    return apology("You don't have that many shares to sell", 400)

            #  if the user removes all stocks, delete stock from table
            for i in portfolio:
                if i["shares"] == shares:
                    db.execute("DELETE FROM portfolio WHERE symbol=:symbol AND userid=:userid", symbol=symbol, userid=session["user_id"])
                    counter += 1

            if counter == 0:
                db.execute("UPDATE portfolio SET shares = shares - :shares WHERE symbol=:symbol AND userid=:userid", shares=shares, symbol=symbol, userid=session["user_id"])

            db.execute("UPDATE users SET cash = cash + :sale WHERE id=:id", sale=sale, id=session["user_id"])
            db.execute("INSERT INTO history (symbol, shares, price, userid) VALUES (:symbol, :shares, :price, :userid)",
                        symbol=symbol,
                        shares=-shares,
                        price=stock["price"],
                        userid=session["user_id"])
            return redirect("/")

    else:
        userStocks = db.execute("SELECT symbol FROM portfolio WHERE userid=:id", id=session["user_id"])
        return render_template("sell.html", userStocks=userStocks)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
