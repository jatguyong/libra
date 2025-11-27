import os
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from google import genai

# Configure application
# Assumes app.py is in 'root', templates in 'root/templates', static in 'root/static'
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

queries, responses = [], []

# Ideally, use os.environ.get("GEMINI_API_KEY") for security
client = genai.Client(api_key="AIzaSyDNU74cC94jpEWUKqgoIAzWWMaHbEjWMI4")

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        query = request.form.get("query")
        
        if query is None:
            flash("Please enter a query.")
            return redirect("/")
        
        queries.append(query)
        
        # Real call to Gemini
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=query,
            )
            responses.append(response.text)
        except Exception as e:
            responses.append(f"Error connecting to AI: {str(e)}")
        
        return render_template("index.html", queries=queries, responses=responses)
    
    else:
        return render_template("index.html", queries=queries, responses=responses)

if __name__ == "__main__":
    app.run(debug=True)