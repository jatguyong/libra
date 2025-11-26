import os

from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

queries, responses = [], []

from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        query = request.form.get("query")
        
        if query is None:
            flash("Please enter a query.")
            return redirect("/")
        
        queries.append(query)
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=query,
        )
        
        responses.append(response.text)
        
        return render_template("index.html", queries=queries, responses=responses)
    
    else:
        return render_template("index.html")
