import os
from dotenv import load_dotenv

# Load environment variables from .env file before anything else
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from flask import Flask, request, jsonify, Response
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
    from prolog_graphrag_pipeline.main_driver import run_pipeline
    
    data = request.json or {}
    react_messages = data.get("messages", [])

    if not react_messages:
        return jsonify({"error": "No messages provided"}), 400

    # Extract the user's latest question
    latest_msg = react_messages[-1]
    question = latest_msg.get("content", "")

    try:
        # Run the Prolog-GraphRAG pipeline
        # flag="x" means default exeuction path
        result = run_pipeline(question, flag="x")
        answer_text = result.get("answer", "No answer generated.")
        
        # Generator to simulate streaming the final answer to the frontend
        def generate():
            # Split the text by spaces safely and yield piece by piece to keep the frontend UI streaming effect
            import time
            words = answer_text.split(" ")
            for word in words:
                yield word + " "
                time.sleep(0.02)
        
        return Response(generate(), mimetype='text/plain')
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Pipeline Error: {e}")
        return jsonify({
            "error": "Failed to process the request through the pipeline.",
            "details": str(e),
            "status": "error"
        }), 503

if __name__ == "__main__":
    app.run(debug=True, port=5000)