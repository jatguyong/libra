import os
import secrets
from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_session import Session
import ollama

app = Flask(__name__)

# --- CONFIGURATION ---
app.config["SECRET_KEY"] = secrets.token_hex(32)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# --- CONSTANTS ---
MODEL_NAME = 'llama3.1:8b-instruct-q4_K_M'

SYSTEM_INSTRUCTION = """
Your responses should be precise, logical, and slightly technical but accessible.
When answering complex queries, briefly outline the logical steps you are taking.
Maintain a professional, helpful, and futuristic persona.
IMPORTANT: NEVER use asterisks, bold or italic formatting in your responses.
IMPORTANT: USE LINE BREAKS IN THE FORM OF <br><br> FREQUENTLY TO IMPROVE READABILITY.
"""

@app.route("/", methods=["GET", "POST"])
def index():
    # Initialize session storage if not present
    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":
        user_input = request.form.get("query")
        
        if not user_input or not user_input.strip():
            return redirect(url_for('index'))

        # Add User Message to History
        session["chat_history"].append({"role": "user", "content": user_input})
        
        try:
            # Prepare messages for Ollama
            messages = [{'role': 'system', 'content': SYSTEM_INSTRUCTION}]
            
            # Add context from history (optional, currently just sending logical pairs for simplicity)
            # For better context, we could loop through session["chat_history"] here.
            messages.append({'role': 'user', 'content': user_input})

            # CALL OLLAMA
            response = ollama.chat(model=MODEL_NAME, messages=messages)
            ai_response = response['message']['content']
            
        except Exception as e:
            print(f"❌ OLLAMA ERROR: {e}")
            ai_response = f"System Error: Unable to connect to inference engine. ({str(e)})"

        # Add AI Message to History
        session["chat_history"].append({"role": "ai", "content": ai_response})
        session.modified = True
        
        return redirect(url_for('index'))

    # GET REQUEST
    return render_template("index.html", chat_history=session["chat_history"])

@app.route("/chat", methods=["POST"])
def chat():
    print("--- CHAT REQUEST RECEIVED ---")
    data = request.json
    print(f"Payload: {data}")
    user_input = data.get("query")
    
    if not user_input:
        print("Error: No query provided")
        return {"error": "No query provided"}, 400

    if "chat_history" not in session:
        session["chat_history"] = []

    session["chat_history"].append({"role": "user", "content": user_input})
    print(f"User Input: {user_input}")

    try:
        messages = [{'role': 'system', 'content': SYSTEM_INSTRUCTION}]
        messages.append({'role': 'user', 'content': user_input})

        print(f"Calling Ollama with model: {MODEL_NAME}")
        # print(f"Messages: {messages}") # Uncomment for full message log

        response = ollama.chat(model=MODEL_NAME, messages=messages)
        print("Ollama response received")
        
        ai_response = response['message']['content']
        print(f"AI Response content length: {len(ai_response)}")
        
    except Exception as e:
        print(f"❌ OLLAMA ERROR: {e}")
        ai_response = f"Error: {str(e)}"
        # Check if it's a connection error
        if "Connection refused" in str(e):
             ai_response += " (Make sure Ollama is running!)"

    session["chat_history"].append({"role": "ai", "content": ai_response})
    session.modified = True

    print("--- CHAT REQUEST COMPLETED ---")
    return {"response": ai_response}

@app.route("/reset", methods=["POST"])
def reset_session():
    session.clear()
    return redirect(url_for('index'))

if __name__ == "__main__":
    print("----------------------------------------------------------------")
    print("   LIBRA SYSTEM STARTING...")
    print("   PLEASE ACCESS VIA: http://127.0.0.1:5000")
    print("   DO NOT USE LIVE SERVER (Port 5500)")
    print("----------------------------------------------------------------")
    app.run(debug=True, port=5000)