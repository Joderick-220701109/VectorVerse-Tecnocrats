import os
from flask import Blueprint, current_app, jsonify, request, g

from ..services.pdf_processing import process_pdf
from ..services.jobs import submit_ingest_job, get_job_status
from ..auth import require_auth
from ..repository.rag_repository import fetch_document_by_hash
import hashlib


bp = Blueprint("ingest", __name__)


@bp.route("/upload", methods=["POST"])
@require_auth
def upload_pdf():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400
        
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400
        
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "Only PDF files are allowed"}), 400

        target_dir = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(target_dir, exist_ok=True)
        
        # Sanitize filename
        safe_filename = os.path.basename(file.filename)
        file_path = os.path.join(target_dir, safe_filename)
        
        file.save(file_path)

        user_id = g.current_user["id"] if isinstance(g.current_user, dict) else g.current_user.get("id")

        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                if not chunk:
                    break
                hasher.update(chunk)
        content_hash = hasher.hexdigest()

        existing = fetch_document_by_hash(int(user_id), content_hash)
        if existing:
            return jsonify({
                "error": "Duplicate document for this user",
                "existing_document_id": existing["id"],
                "existing_filename": existing["filename"],
                "can_replace": True,
            }), 409

        ingestion_result = process_pdf(file_path, safe_filename, owner_user_id=int(user_id), content_hash=content_hash)
        
        return jsonify({
            "message": f"{safe_filename} processed successfully!",
            "filename": safe_filename,
            "document_id": ingestion_result["document_id"],
            "chunks_stored": ingestion_result["text_chunks"],
            "images_stored": ingestion_result["image_chunks"],
        }), 200
    
    except Exception as e:
        return jsonify({"error": f"Failed to process PDF: {str(e)}"}), 500


@bp.route("/upload_async", methods=["POST"])
@require_auth
def upload_pdf_async():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "Only PDF files are allowed"}), 400

        target_dir = current_app.config["UPLOAD_FOLDER"]
        os.makedirs(target_dir, exist_ok=True)
        safe_filename = os.path.basename(file.filename)
        file_path = os.path.join(target_dir, safe_filename)
        file.save(file_path)

        user_id = g.current_user["id"] if isinstance(g.current_user, dict) else g.current_user.get("id")

        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b''):
                if not chunk:
                    break
                hasher.update(chunk)
        content_hash = hasher.hexdigest()

        existing = fetch_document_by_hash(int(user_id), content_hash)
        if existing:
            return jsonify({
                "error": "Duplicate document for this user",
                "existing_document_id": existing["id"],
                "existing_filename": existing["filename"],
                "can_replace": True,
            }), 409

        job_id = submit_ingest_job(file_path, safe_filename, owner_user_id=int(user_id), content_hash=content_hash)
        return jsonify({
            "message": f"Accepted {safe_filename} for background processing",
            "job_id": job_id,
            "filename": safe_filename,
            "status_url": f"/api/jobs/{job_id}",
        }), 202
    except Exception as e:
        return jsonify({"error": f"Failed to enqueue PDF: {str(e)}"}), 500


@bp.route("/jobs/<job_id>", methods=["GET"])
@require_auth
def get_job(job_id: str):
    try:
        status = get_job_status(job_id)
        return jsonify(status), 200 if status.get("state") != "not_found" else 404
    except Exception as e:
        return jsonify({"error": f"Failed to fetch job status: {str(e)}"}), 500
