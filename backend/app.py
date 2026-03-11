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
        # flag="x" means default execution path
        result = run_pipeline(question, flag="x")

        # Safely convert contexts to strings if they are objects
        raw_contexts = result.get("contexts", [])
        if isinstance(raw_contexts, list):
            contexts = [str(c) for c in raw_contexts]
        else:
            contexts = str(raw_contexts) if raw_contexts else ""

        return jsonify({
            "answer": result.get("answer", "No answer generated."),
            "explainer_output": result.get("explainer_output", ""),
            "prolog_explanation": result.get("prolog_explanation", ""),
            "database": result.get("database", ""),
            "query": result.get("query", ""),
            "contexts": contexts,
            "condensed_context": result.get("condensed_context", ""),
            "fallback": result.get("fallback", "unknown"),
            "prolog_error": result.get("prolog_error", None),
        })
        
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