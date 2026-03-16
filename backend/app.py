import os
import json
import queue
import threading
import logging

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "http://localhost:5173")
CORS(app, resources={r"/*": {"origins": CORS_ORIGIN}})

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "Libra API Active"})

@app.route("/api/health", methods=["GET"])
def health():
    """Health check endpoint for Docker and monitoring."""
    health_status = {"api": "ok"}
    try:
        from prolog_graphrag_pipeline.graphrag.graphrag_driver import ensure_driver_connected
        ensure_driver_connected()
        health_status["neo4j"] = "ok"
    except Exception as e:
        health_status["neo4j"] = f"error: {e}"
    return jsonify(health_status)


# --- PDF Ingestion state tracking ---
_ingestion_status = {}  # {filename: {status, duration_s, error}}
_cancellation_flags = {}  # {filename: threading.Event}
_ingestion_lock = threading.Lock()


@app.route("/api/ingest", methods=["POST"])
def ingest():
    if "files" not in request.files:
        return jsonify({"error": "No files part in the request"}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No selected files"}), 400

    upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    saved_files = []
    for file in files:
        if file.filename:
            safe_name = secure_filename(file.filename)
            filepath = os.path.join(upload_dir, safe_name)
            file.save(filepath)
            saved_files.append({"filename": safe_name, "filepath": filepath})
            cancel_event = threading.Event()
            with _ingestion_lock:
                _ingestion_status[safe_name] = {"status": "processing", "duration_s": 0}
                _cancellation_flags[safe_name] = cancel_event

    # Trigger KG ingestion in a background thread

    def _bg_ingest(file_list):
        from prolog_graphrag_pipeline.graphrag import graphrag_driver as gd
        file_paths = [f["filepath"] for f in file_list]
        try:
            results = gd.ingest_pdf_files(file_paths)
            for r in results:
                fname = os.path.basename(r["file"])
                with _ingestion_lock:
                    flag = _cancellation_flags.get(fname)
                # If cancelled mid-run, clean up the partial data
                if flag and flag.is_set():
                    logger.info(f"Cancellation detected post-ingest for {fname}. Cleaning up...")
                    try:
                        result = gd.remove_document_from_kg(fname)
                        logger.info(f"Cancel cleanup result for {fname}: {result}")
                    except Exception as ex:
                        logger.error(f"Cancel cleanup error for {fname}: {ex}")
                    # File already removed by /api/ingest/cancel, skip status update
                    continue
                with _ingestion_lock:
                    _ingestion_status[fname] = {
                        "status": r.get("status", "done"),
                        "duration_s": r.get("duration_s", 0),
                        "error": r.get("error"),
                    }
        except Exception as e:
            logger.error(f"Background ingestion error: {e}")
            with _ingestion_lock:
                for f in file_list:
                    _ingestion_status[f["filename"]] = {"status": "error", "error": str(e)}

    thread = threading.Thread(target=_bg_ingest, args=(saved_files,), daemon=True)
    thread.start()

    return jsonify({
        "message": f"Uploaded {len(saved_files)} file(s). Ingestion started in background.",
        "files": [f["filename"] for f in saved_files]
    })

@app.route("/api/ingest/status", methods=["GET"])
def ingest_status():
    """Return current ingestion status for all tracked files."""
    with _ingestion_lock:
        return jsonify(_ingestion_status)

@app.route("/api/ingest/cancel", methods=["POST"])
def cancel_ingest():
    """Signal cancellation for an ongoing ingestion. The background thread will clean up."""
    data = request.json or {}
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    with _ingestion_lock:
        flag = _cancellation_flags.get(filename)
        status = _ingestion_status.get(filename, {})

    if flag:
        flag.set()
        logger.info(f"Cancellation requested for: {filename}")

    if status.get("status") != "processing":
        # Already done — just do a regular remove instead
        return cancel_and_remove(filename)

    return jsonify({"message": f"Cancellation signal sent for {filename}"})

def cancel_and_remove(filename: str):
    """Remove a document from Neo4j and disk, with debug output."""
    from prolog_graphrag_pipeline.graphrag import graphrag_driver as gd
    logger.info(f"Removing document: {filename}")
    result = gd.remove_document_from_kg(filename)
    logger.info(f"Removal result: {result}")

    upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
    filepath = os.path.join(upload_dir, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        logger.info(f"File deleted from disk: {filepath}")
    else:
        logger.info(f"File not on disk (already gone): {filepath}")

    with _ingestion_lock:
        _ingestion_status.pop(filename, None)
        _cancellation_flags.pop(filename, None)

    return jsonify(result)

@app.route("/api/ingest/remove", methods=["POST"])
def remove_document():
    """Remove a specific document and its chunks from Neo4j."""
    data = request.json or {}
    filename = data.get("filename")
    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    # If still processing, signal cancellation first
    with _ingestion_lock:
        flag = _cancellation_flags.get(filename)
        status = _ingestion_status.get(filename, {}).get("status")
    if flag and status == "processing":
        flag.set()
        logger.info(f"Cancellation flagged for in-progress ingest: {filename}")

    return cancel_and_remove(filename)

@app.route("/api/ingest/documents", methods=["GET"])
def list_documents():
    """List all documents currently ingested in the Neo4j knowledge graph."""
    from prolog_graphrag_pipeline.graphrag.graphrag_driver import list_ingested_documents
    docs = list_ingested_documents()
    return jsonify({"documents": docs})

@app.route("/api/chat", methods=["POST"])
def chat():
    from prolog_graphrag_pipeline.main_driver import run_pipeline
    
    data = request.json or {}
    react_messages = data.get("messages", [])

    if not react_messages:
        return jsonify({"error": "No messages provided"}), 400

    latest_msg = react_messages[-1]
    question = latest_msg.get("content", "")
    use_global_kg = data.get("useGlobalKG", False)

    import traceback as tb_module

    def generate_events():
        q = queue.Queue()

        def status_callback(status_data):
            q.put(status_data)

        def worker():
            try:
                # Run the Prolog-GraphRAG pipeline with the callback
                result = run_pipeline(question, flag="x", sample_mode=True, use_global_kg=use_global_kg, status_callback=status_callback)

                # Safely convert contexts to strings if they are objects
                raw_contexts = result.get("contexts", [])
                if isinstance(raw_contexts, list):
                    contexts = [str(c) for c in raw_contexts]
                else:
                    contexts = str(raw_contexts) if raw_contexts else ""

                best_answer_obj = result.get("best_answer")
                if best_answer_obj and isinstance(best_answer_obj, dict):
                    answer_text = best_answer_obj.get("text_answer", result.get("answer", "No answer generated."))
                    answer_logprobs = best_answer_obj.get("logprobs", [])
                else:
                    answer_text = result.get("answer", "No answer generated.")
                    # result["logprobs"] is a list-of-lists (one per sample); grab the first if available
                    raw_lp = result.get("logprobs", [])
                    if raw_lp and isinstance(raw_lp, list) and len(raw_lp) > 0 and isinstance(raw_lp[0], list):
                        answer_logprobs = raw_lp[0]
                    else:
                        answer_logprobs = raw_lp if isinstance(raw_lp, list) else []

                q.put({
                    "type": "result",
                    "data": {
                        "answer": answer_text,
                        "logprobs": answer_logprobs,
                        "semantic_entropy": result.get("semantic_entropy"),
                        "hallucination_flag": result.get("hallucination_flag"),
                        "explainer_output": result.get("explainer_output", ""),
                        "prolog_explanation": result.get("prolog_explanation", ""),
                        "database": result.get("database", ""),
                        "prolog_query": result.get("prolog_query", ""),
                        "query": result.get("query", ""),
                        "contexts": contexts,
                        "condensed_context": result.get("condensed_context", ""),
                        "fallback": result.get("fallback", "unknown"),
                        "prolog_error": result.get("prolog_error", None)
                    }
                })
                
            except Exception as e:
                tb_module.print_exc()
                logger.error(f"Pipeline Error: {e}")
                q.put({"type": "error", "error": "Failed to process the request through the pipeline.", "details": str(e)})

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

        while True:
            item = q.get()
            yield f"data: {json.dumps(item)}\n\n"
            if item.get("type") in ("result", "error"):
                break

    return Response(generate_events(), mimetype='text/event-stream')

if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
    )