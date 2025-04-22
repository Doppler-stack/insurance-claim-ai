# utils.py
import logging
import os
import shutil

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile
# Optional: only if you're using PDF conversion
from pdf2image import convert_from_path
from PIL import Image
from sqlalchemy.orm import Session

from database import engine  # Make sure this points to your existing engine
from models import Claim


def get_claim_or_404(claim_id: int, db: Session) -> Claim:
    """Retrieve a claim by ID or raise a 404 error."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        # Note: We use a detailed dict here to support structured errors
        raise HTTPException(
            status_code=404,
            detail={
                "error": "CLAIM_NOT_FOUND",
                "message": f"No claim found with ID {claim_id}",
            },
        )
    return claim


def delete_file_if_exists(file_path: str) -> None:
    """Deletes a file if it exists and logs the outcome."""
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            logging.info(f"[FILE_DELETED] Path='{file_path}'")
        except Exception as e:
            # Not critical if delete fails, but still worth logging
            logging.warning(f"[FILE_DELETE_FAILED] Path='{file_path}' — {e}")
    else:
        # File probably already gone — no big deal
        logging.info(f"[FILE_NOT_FOUND] Nothing to delete at '{file_path}'")


# Helper to write uploaded file to disk
async def save_uploaded_file(file: UploadFile, mime_type: str) -> str:
    # Just making sure the upload folder exists (or gets made if not)
    target_folder = "uploads"
    os.makedirs(
        target_folder, exist_ok=True
    )  # quietly does nothing if it already exists

    # Full destination path for where we'll save the file
    full_path = os.path.join(target_folder, file.filename)

    # Actually save the file by writing its binary content
    with open(full_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Not doing any post-processing here yet, just giving the final path back
    return full_path


def is_using_postgres() -> bool:
    """Check if the app is connected to a PostgreSQL database."""
    return engine.url.drivername.startswith("postgresql")
