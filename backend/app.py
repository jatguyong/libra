import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import ollama

app = Flask(__name__)

# Configure CORS to allow requests ONLY from http://localhost:5173
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}})

# Constants
MODEL_NAME = 'gemma3:1b'

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
    data = request.json or {}
    react_messages = data.get("messages", [])

    # Create a new list for Ollama, starting with the SYSTEM_INSTRUCTION
    ollama_messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTION}
    ]

    # Loop through the incoming React messages array
    for msg in react_messages:
        role = msg.get("role")
        content = msg.get("content", "")

        # Crucial: If a message has role: 'ai', change it to role: 'assistant'
        if role == "ai":
            role = "assistant"
            
        ollama_messages.append({
            "role": role,
            "content": content
        })

    try:
        # Calls ollama.chat
        response = ollama.chat(model=MODEL_NAME, messages=ollama_messages)
        
        # Extracts the response text
        ai_response = response['message']['content']
        
        return jsonify({
            "response": ai_response,
            "status": "success"
        })
        
    except Exception as e:
        # Uses a try/except block to gracefully return a JSON error if Ollama is not running
        print(f"Ollama Error: {e}")
        return jsonify({
            "error": "Failed to connect to Ollama or process request. Is Ollama running?",
            "details": str(e),
            "status": "error"
        }), 503

if __name__ == "__main__":
    app.run(debug=True, port=5000)