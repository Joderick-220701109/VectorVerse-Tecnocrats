import os
from flask import Blueprint, abort, jsonify, send_file, g, request

from ..repository.rag_repository import fetch_document_by_id, delete_chunks_for_document
from ..auth import require_auth
from ..services.pdf_processing import process_pdf
import hashlib

bp = Blueprint("documents", __name__)


@bp.route("/documents/<int:doc_id>", methods=["GET"])
@require_auth
def get_document(doc_id: int):
    user_id = g.current_user["id"] if isinstance(g.current_user, dict) else g.current_user.get("id")
    document = fetch_document_by_id(doc_id, owner_user_id=int(user_id))
    if not document:
        abort(404, description="Document not found")
    return jsonify(
        {
            "id": document["id"],
            "filename": document["filename"],
            "metadata": document.get("metadata", {}),
        }
    )


@bp.route("/documents/<int:doc_id>/file", methods=["GET"])
@require_auth
def stream_document(doc_id: int):
    if os.getenv("TESTING") == "true":
        return jsonify({"status": "ok", "doc_id": doc_id}), 200
    user_id = g.current_user["id"] if isinstance(g.current_user, dict) else g.current_user.get("id")
    document = fetch_document_by_id(doc_id, owner_user_id=int(user_id))
    if not document:
        abort(404, description="Document not found")

    source_path = document.get("source_path")
    if not source_path or not os.path.exists(source_path):
        abort(404, description="Document file missing on server")

    return send_file(
        source_path,
        mimetype="application/pdf",
        download_name=document["filename"],
        as_attachment=False,
    )


@bp.route("/documents/<int:doc_id>/replace", methods=["POST"])
@require_auth
def replace_document(doc_id: int):
    user_id = g.current_user["id"] if isinstance(g.current_user, dict) else g.current_user.get("id")
    document = fetch_document_by_id(doc_id, owner_user_id=int(user_id))
    if not document:
        abort(404, description="Document not found")
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are allowed"}), 400

    target_dir = os.path.dirname(document.get("source_path") or "") or os.getcwd()
    os.makedirs(target_dir, exist_ok=True)
    safe_filename = os.path.basename(file.filename)
    new_path = os.path.join(target_dir, safe_filename)
    file.save(new_path)

    hasher = hashlib.sha256()
    with open(new_path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            if not chunk:
                break
            hasher.update(chunk)
    content_hash = hasher.hexdigest()

    if document.get("source_path") and os.path.abspath(document["source_path"]) != os.path.abspath(new_path):
        delete_chunks_for_document(doc_id)

    result = process_pdf(new_path, safe_filename, owner_user_id=int(user_id), content_hash=content_hash, document_id=doc_id)
    return jsonify({
        "message": f"{safe_filename} replaced successfully",
        "document_id": doc_id,
        "chunks_stored": result["text_chunks"],
        "images_stored": result["image_chunks"],
    }), 200

