import os
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from google import genai
from google.genai import types

app = Flask(__name__)

# Configure session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

queries, responses = [], []

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SYSTEM_INSTRUCTION = """
Your responses should be precise, logical, and slightly technical but accessible.
When answering complex queries, briefly outline the logical steps you are taking.
Maintain a professional, helpful, and futuristic persona.
IMPORTANT: NEVER use asterisks, bold or italic formatting in your responses.
IMPORTANT: USE LINE BREAKS IN THE FORM OF <br><br> FREQUENTLY TO IMPROVE READABILITY.
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        query = request.form.get("query")
        
        if not query:
            flash("Please enter a query.")
            return redirect("/")
        
        queries.append(query)
        
        try:
            # Call Gemini with System Instructions
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=query,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.7, # Adjust creativity (0.0 = strict, 1.0 = creative)
                )
            )
            response_text = response.text
        except Exception as e:
            response_text = f"Error connecting to AI: {str(e)}"
        
        responses.append(response_text)
        
        return render_template("index.html", queries=queries, responses=responses)
    
    else:
        return render_template("index.html", queries=queries, responses=responses)

if __name__ == "__main__":
    app.run(debug=True)