import os
import secrets
from flask import Flask, request, jsonify, session
from flask_session import Session
from flask_cors import CORS
import ollama

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}})

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

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Libra API Active"})

@app.route("/api/chat", methods=["POST"])
def chat():
    print("--- CHAT REQUEST RECEIVED ---")
    data = request.json or {}
    print(f"Payload: {data}")
    
    user_input = data.get("message")
    mode = data.get("mode", "default")
    
    if not user_input:
        print("Error: No message provided")
        return jsonify({"error": "No message provided"}), 400

    print(f"User Input: {user_input}, Mode: {mode}")

    # Dummy structured JSON response
    ai_response = f"This is a dummy response from the Libra API. You said: '{user_input}' in mode: '{mode}'."

    print("--- CHAT REQUEST COMPLETED ---")
    return jsonify({"response": ai_response, "status": "success"})

if __name__ == "__main__":
    print("----------------------------------------------------------------")
    print("   LIBRA SYSTEM STARTING...")
    print("   PLEASE ACCESS VIA: http://127.0.0.1:5000")
    print("   DO NOT USE LIVE SERVER (Port 5500)")
    print("----------------------------------------------------------------")
    app.run(debug=True, port=5000)