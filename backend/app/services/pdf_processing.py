import pdfplumber
from typing import Dict, List, Optional

from ..config import Config
from ..db import connect_db
from ..repository.rag_repository import insert_document, update_document_metadata
from .embedding import embed_image_from_stream, embed_text


def chunk_text(text: str, chunk_size: Optional[int] = None, overlap: Optional[int] = None) -> List[str]:
    """Split text into overlapping chunks."""
    chunk_size = chunk_size or Config.CHUNK_SIZE
    overlap = overlap or Config.CHUNK_OVERLAP
    words = text.split()
    chunks: List[str] = []
    i = 0
    while i < len(words):
        chunk = words[i : i + chunk_size]
        chunks.append(" ".join(chunk))
        i += max(chunk_size - overlap, 1)
    return chunks


def process_pdf(file_path: str, original_filename: str, owner_user_id: int, content_hash: str, document_id: int | None = None) -> Dict[str, int]:
    """Process PDF, store embeddings, and return ingestion metadata."""
    conn = connect_db()
    print("✅ Connected to PostgreSQL database.")

    if document_id is None:
        document_id = insert_document(
            conn,
            filename=original_filename,
            source_path=file_path,
            owner_user_id=owner_user_id,
            content_hash=content_hash,
            metadata={"source": "pdf_upload"},
        )
    else:
        update_document_metadata(document_id, original_filename, file_path, content_hash, {"source": "pdf_replace"})

    text_chunk_count = 0
    image_chunk_count = 0

    with pdfplumber.open(file_path) as pdf:
        total_pages = len(pdf.pages)
        max_pages = Config.MAX_PAGES_PER_DOC or total_pages
        for page_num, page in enumerate(pdf.pages[:max_pages], start=1):
            print(f"🔍 Processing page {page_num}...")
            page_text_chunks = chunk_text(page.extract_text() or "")
            last_text_chunk_id: Optional[int] = None

            for idx, chunk in enumerate(page_text_chunks, start=1):
                metadata = {
                    "type": "text",
                    "page": page_num,
                    "chunk": idx,
                    "filename": original_filename,
                }
                last_text_chunk_id = embed_text(
                    conn,
                    chunk,
                    document_id=document_id,
                    page_number=page_num,
                    chunk_index=idx,
                    metadata=metadata,
                )
                text_chunk_count += 1

            # Try multiple methods to extract images from PDF
            images_extracted = False
            
            # Method 1: Use pdfplumber's image extraction (handles decoding better)
            try:
                page_images = page.images
                for i, img_info in enumerate(page_images, start=1):
                    if not Config.ENABLE_IMAGE_EMBEDDING:
                        break
                    try:
                        # Try to get the image using pdfplumber's method
                        # This handles PDF filters and decoding automatically
                        img_name = f"{original_filename}_page_{page_num}_img_{i}.png"
                        
                        # Get image stream - pdfplumber images dict may have stream or we need to access via objects
                        stream = None
                        stream_data = None
                        
                        # Try to get stream from image info
                        if "stream" in img_info:
                            stream = img_info["stream"]
                        else:
                            # Fallback: try to find stream in page objects
                            img_objects = page.objects.get("image", [])
                            if i <= len(img_objects):
                                stream = img_objects[i - 1].get("stream")
                        
                        if stream is None:
                            continue
                        
                        # Try to get decoded data
                        try:
                            if hasattr(stream, "get_data"):
                                stream_data = stream.get_data()
                            elif isinstance(stream, dict):
                                stream_data = stream.get("data", b"")
                                if isinstance(stream_data, str):
                                    stream_data = stream_data.encode()
                            else:
                                stream_data = bytes(stream)
                        except Exception as e:
                            print(f"⚠️ Could not get stream data for {img_name}: {e}")
                            continue
                        
                        if not stream_data or len(stream_data) == 0:
                            continue
                        
                        metadata = {
                            "type": "image",
                            "page": page_num,
                            "image_width": img_info.get("width"),
                            "image_height": img_info.get("height"),
                            "x0": img_info.get("x0"),
                            "y0": img_info.get("y0"),
                            "x1": img_info.get("x1"),
                            "y1": img_info.get("y1"),
                            "filename": img_name,
                        }
                        
                        result = embed_image_from_stream(
                            conn,
                            stream_data,
                            img_name,
                            document_id=document_id,
                            page_number=page_num,
                            chunk_index=i,
                            linked_chunk_id=last_text_chunk_id,
                            metadata=metadata,
                        )
                        
                        if result:
                            image_chunk_count += 1
                            images_extracted = True
                    except Exception as exc:
                        print(f"⚠️ Failed to extract image {i} on page {page_num}: {exc}")
                        continue
            except Exception as exc:
                print(f"⚠️ Failed to extract images from page {page_num} using pdfplumber images: {exc}")
            
            # Method 2: Fallback to objects.get("image") if Method 1 didn't work
            if not images_extracted and Config.ENABLE_IMAGE_EMBEDDING:
                try:
                    for i, img_obj in enumerate(page.objects.get("image", []), start=1):
                        try:
                            stream = img_obj.get("stream")
                            if stream is None:
                                continue
                            
                            # Try multiple ways to get the stream data
                            try:
                                stream_data = stream.get_data()
                            except Exception:
                                try:
                                    stream_data = bytes(stream.get("data", b""))
                                except Exception:
                                    # Try accessing raw stream
                                    if hasattr(stream, "get_data"):
                                        stream_data = stream.get_data()
                                    else:
                                        stream_data = bytes(stream)
                            
                            if not stream_data or len(stream_data) == 0:
                                continue
                            
                            img_name = f"{original_filename}_page_{page_num}_img_{i}.png"
                            metadata = {
                                "type": "image",
                                "page": page_num,
                                "image_width": img_obj.get("width"),
                                "image_height": img_obj.get("height"),
                                "filename": img_name,
                            }
                            
                            result = embed_image_from_stream(
                                conn,
                                stream_data,
                                img_name,
                                document_id=document_id,
                                page_number=page_num,
                                chunk_index=i,
                                linked_chunk_id=last_text_chunk_id,
                                metadata=metadata,
                            )
                            
                            if result:
                                image_chunk_count += 1
                        except Exception as exc:
                            print(f"⚠️ Failed to extract image {i} on page {page_num} (fallback method): {exc}")
                            continue
                except Exception as exc:
                    print(f"⚠️ Failed to extract images from page {page_num} using objects method: {exc}")

    conn.close()
    print("🔒 Database connection closed.")

    return {
        "document_id": document_id,
        "text_chunks": text_chunk_count,
        "image_chunks": image_chunk_count,
    }
