# utils.py
import logging
import os
import re

import pytesseract
from dotenv import load_dotenv
from fastapi import HTTPException
# Optional: only if you're using PDF conversion
from pdf2image import convert_from_path
from PIL import Image

from models import Claim

# Load environment variables from .env file
load_dotenv()

# Pull in paths from environment or fallback to defaults
tesseract_cmd = os.getenv(
    "TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)
poppler_path = os.getenv("POPPLER_PATH", r"C:\ProgramData\chocolatey\lib\poppler\tools")


# Check for actual existence of the tesseract executable
if not os.path.exists(tesseract_cmd):
    raise RuntimeError(
        f"Tesseract executable not found at: {tesseract_cmd}\n"
        "Tip: Check your .env file or install path. You can override this using the TESSERACT_CMD variable."
    )

# Set the OCR engine's command path
pytesseract.pytesseract.tesseract_cmd = tesseract_cmd


def create_claim(db, claimant_name, claim_type, amount, description, file_path):
    # Create a new Claim object — standard ORM stuff
    claim = Claim(
        claimant_name=claimant_name,
        claim_type=claim_type,
        amount=amount,
        description=description,
        document_path=file_path,
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)  # Refresh to get updated fields like ID
    return claim


def update_claim_status(claim, new_status, db):
    # Change the status and persist it — minimal validation here
    claim.status = new_status
    db.commit()  # Future: maybe wrap in a try/except or add audit logging


def delete_claim(claim, db):
    # Remove the claim from DB — doesn't touch file system!
    db.delete(claim)
    db.commit()


def parse_claim_text(text: str) -> dict:
    """
    Very basic parser to extract claim_type and amount from OCR text.
    Example expected format:
        Claim Type: Travel
        Amount: $120.00
    """
    claim_type = None
    amount = None

    # Extract "Claim Type: Something"
    type_match = re.search(r"Claim\s*Type\s*:\s*(\w+)", text, re.IGNORECASE)
    if type_match:
        claim_type = type_match.group(1)

    # Extract "Amount: $XXX.XX"
    amount_match = re.search(r"Amount\s*:\s*\$?([\d,]+\.\d{2})", text, re.IGNORECASE)
    if amount_match:
        amount = float(amount_match.group(1).replace(",", ""))

    return {"claim_type": claim_type, "amount": amount}


def extract_text_from_file(file_path: str) -> str:
    """Extract text from supported file types: images, PDFs, plain text."""
    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext in [".png", ".jpg", ".jpeg"]:
            # OCR works natively with image files — no prep needed
            text = pytesseract.image_to_string(Image.open(file_path))

        elif ext == ".pdf":
            # PDFs need conversion — we're using Poppler for that
            pages = convert_from_path(file_path, poppler_path=poppler_path)
            text = "\n".join([pytesseract.image_to_string(page) for page in pages])

        elif ext == ".txt":
            # No OCR needed — just read the raw text
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()

        else:
            # Not a file type we currently support
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}",
            )

        return text

    except Exception as e:
        logging.error(f"[OCR_ERROR] Failed to extract text: {e}")
        # Might want to expand this to handle per-file-type errors more gracefully
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {str(e)}")
