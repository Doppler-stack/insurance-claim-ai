from dotenv import load_dotenv

load_dotenv()


import logging
import os
from typing import List, Optional  # Built-in Python typing

import magic  # Requires installing 'python-magic'
import uvicorn
from fastapi import (Body, Depends, FastAPI, File, Form, HTTPException, Path,
                     Query, Security, UploadFile)
from fastapi.responses import (  # Still part of FastAPI, so grouped after typing
    FileResponse, JSONResponse)
from fastapi.security import APIKeyHeader
from sqlalchemy import func, or_
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.sql import text
from starlette.middleware.cors import CORSMiddleware

from auth import require_api_key
from database import SessionLocal  # This is our DB session dependency
from database import engine, get_db
from models import Claim, ClaimStatus
from rate_limiter import rate_limiter
from routers.admin import admin_router
from schemas import (APIResponse, ClaimAnalysisResponse, ClaimCreate, ClaimOut,
                     StatusUpdate)
from services import create_claim
from services import delete_claim as service_delete_claim
from services import extract_text_from_file, parse_claim_text
from services import update_claim_status as service_update_status
from utils import (delete_file_if_exists, get_claim_or_404, is_using_postgres,
                   save_uploaded_file)

auth_stack = [Depends(require_api_key), Depends(rate_limiter)]


# Initialize FastAPI app
app = FastAPI(
    title="Insurance Claim AI",
    description="A backend for handling file uploads and system health checks.",
    version="1.0.0",
)

app.include_router(admin_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Open for now — lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up logging (basic for now, can tweak later if needed)
logging.basicConfig(
    level=logging.DEBUG,  # this shows DEBUG, INFO, WARNING, etc.
    format="%(asctime)s - %(levelname)s - %(message)s",
)


# Ensure the upload directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Whitelist of MIME types and size caps — tweak as needed for new formats
ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "application/pdf", "text/plain"}
FILE_SIZE_LIMITS = {
    "image/png": 15 * 1024 * 1024,  # 15MB
    "image/jpeg": 15 * 1024 * 1024,  # 15MB
    "application/pdf": 20 * 1024 * 1024,  # 20MB - PDF gets some extra room
    "text/plain": 5 * 1024 * 1024,  # 5MB - tiny limit for text
}


@app.get("/")
async def home():
    """Basic health check to ensure the server is running."""
    try:
        if not os.path.exists(UPLOAD_DIR):
            raise RuntimeError(
                "Uploads folder is missing!"
            )  # Simulated error for testing

        logging.info("Home route accessed successfully.")
        return {"status": "success", "message": "FastAPI server is up and running!"}

    except Exception as e:
        logging.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Health check failed. Server might be experiencing issues.",
        )


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Advanced system health check: verifies database and storage."""
    try:
        # Ensure upload folder exists
        if not os.path.exists(UPLOAD_DIR):
            raise RuntimeError("Uploads folder is missing!")

        # Run a tiny query to confirm DB is reachable
        db.execute(text("SELECT 1"))  # Simple query to check DB connectivity

        logging.info("System health check passed.")
        return {
            "status": "success",
            "message": "Server, database, and storage are all operational.",
            "db_driver": engine.url.drivername,
        }

    except OperationalError:
        logging.error("Database connection failed!")
        raise HTTPException(status_code=500, detail="Database connection error.")

    except Exception as e:
        logging.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=500, detail="Unexpected issue detected in health check."
        )


@app.post(
    "/claims",
    response_model=APIResponse[ClaimOut],
    dependencies=[Depends(require_api_key)],
    summary="Create a claim via JSON",
    description="Create a new claim without uploading a file. Use for API-to-API submission or admin tasks.",
)
def create_claim_from_json(
    payload: ClaimCreate,
    db: Session = Depends(get_db),
):
    """
    Adds a claim based on JSON input instead of file upload.
    """
    claim = create_claim(
        db=db,
        claimant_name=payload.claimant_name,
        claim_type=payload.claim_type,
        amount=payload.amount,
        description=payload.description,
        document_path=None,  # No document for JSON-based creation
    )

    logging.info(f"[CLAIM_CREATED_JSON] ID={claim.id}, type='{claim.claim_type}'")

    return APIResponse(
        status="success",
        data=ClaimOut.model_validate(claim),
    )


@app.post(
    "/upload/",
    response_model=APIResponse[ClaimOut],
    summary="Upload a new claim and document",
)
async def upload_file(
    claimant_name: str = Query(..., description="Name of the claimant"),
    claim_type: str = Query(..., description="Type of the claim"),
    amount: float = Query(..., description="Amount being claimed"),
    description: str = Query(None, description="Optional description of the claim"),
    file: UploadFile = File(..., description="Document file to upload (PDF or image)"),
    db: Session = Depends(get_db),
):
    """Handles file uploads with MIME type and size validation."""

    temp_file_path = os.path.join(UPLOAD_DIR, file.filename)

    try:
        # Save file temporarily
        with open(temp_file_path, "wb") as f:
            f.write(await file.read())

        # Detect MIME type from saved file
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(temp_file_path)

        # Validate MIME type
        if mime_type not in FILE_SIZE_LIMITS:
            os.remove(temp_file_path)  # Cleanup invalid file
            logging.warning(
                f"Upload rejected: {file.filename} (Unknown MIME: {mime_type})"
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_FILE_TYPE",
                    "message": f"File type '{mime_type}' is not allowed. Allowed types: {list(ALLOWED_MIME_TYPES)}",
                },
            )

        # Check file size limit
        max_size = FILE_SIZE_LIMITS[
            mime_type
        ]  # This is safe since we checked existence above
        file_size = os.path.getsize(temp_file_path)

        if file_size > max_size:
            os.remove(temp_file_path)
            logging.warning(
                f"Upload rejected: {file.filename} (Too large: {file_size} bytes)"
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "FILE_TOO_LARGE",
                    "message": f"File exceeds limit. Max allowed: {max_size / (1024 * 1024)}MB",
                },
            )

        # Save file to disk (returns full path)
        saved_path = save_uploaded_file(
            file, mime_type
        )  # Not renaming files for now — revisit if needed

        # Store metadata in DB
        claim = create_claim(
            db, claimant_name, claim_type, amount, description, saved_path
        )

        logging.info(
            f"[CLAIM_CREATED] ID={claim.id}, file='{file.filename}', status='{claim.status.value}'"
        )

        return APIResponse(status="success", data=ClaimOut.model_validate(claim))

    except Exception as e:
        logging.error(f"File upload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "UPLOAD_FAILED",
                "message": "File upload failed due to an internal error.",
            },
        )


# PATCH: Easily update status without resubmitting entire claim
# Accepts raw string and maps it to the Enum (case-insensitive)
@app.patch(
    "/claims/{claim_id}/status",
    response_model=APIResponse[ClaimOut],
    summary="Update claim status",
)
def patch_claim_status(
    claim_id: int, update: StatusUpdate, db: Session = Depends(get_db)
):
    """Update the status of a claim using ClaimStatus enum."""
    claim = get_claim_or_404(claim_id, db)

    # Extract enum safely (already validated by schema)
    status_enum = update.new_status

    service_update_status(claim, status_enum, db)
    db.refresh(claim)

    logging.info(
        f"[CLAIM_STATUS_UPDATED] ID={claim_id}, new_status='{status_enum.value}'"
    )
    return {"status": "success", "data": ClaimOut.model_validate(claim)}


@app.get(
    "/claims",
    response_model=APIResponse[List[ClaimOut]],
    dependencies=auth_stack,
    summary="List all submitted claims",
)
def list_claims(
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(10, ge=1, le=100, description="Max records to return"),
    status: Optional[str] = Query(None, description="Filter by claim status"),
    claimant_name: Optional[str] = Query(None, description="Search by claimant name"),
    db: Session = Depends(get_db),
):
    """
    List submitted claims with optional filters and pagination.
    """
    query = db.query(Claim)

    # Filter by status if provided (case-insensitive)
    if status:
        try:
            status_enum = ClaimStatus[
                status.upper()
            ]  # Could wrap this in helper if we add more enums later
            query = query.filter(Claim.status == status_enum)
        except KeyError:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_STATUS_FILTER",
                    "message": f"Invalid status filter '{status}'. Must be one of: {[s.name for s in ClaimStatus]}",
                },
            )

    # Search by claimant name if provided (case-insensitive partial match)
    if claimant_name:
        query = query.filter(Claim.claimant_name.ilike(f"%{claimant_name}%"))

    claims = query.offset(skip).limit(limit).all()

    logging.info(
        f"Retrieved {len(claims)} claim(s) [skip={skip}, limit={limit}, filters={{status: {status}, name: {claimant_name}}}]"
    )

    return APIResponse(
        status="success", data=[ClaimOut.model_validate(c) for c in claims]
    )


@app.get(
    "/download/{claim_id}",
    response_class=FileResponse,
    summary="Download uploaded file for a claim",
)
def download_file(
    claim_id: int = Path(..., description="ID of the claim to download file for"),
    db: Session = Depends(get_db),
):
    """
    Downloads the uploaded file associated with a given claim.
    """
    claim = get_claim_or_404(claim_id, db)

    if not claim.document_path or not os.path.exists(claim.document_path):
        # Could add backup storage logic here (e.g., S3 fallback or retry mechanism)
        raise HTTPException(
            status_code=404,
            detail={
                "error": "FILE_NOT_FOUND",
                "message": f"No uploaded file found for claim ID {claim_id}.",
            },
        )

    logging.info(f"Downloading file for claim ID {claim_id}: {claim.file_name}")

    return FileResponse(
        path=claim.document_path,
        filename=os.path.basename(claim.document_path),
        media_type="application/octet-stream",
    )


# --------------------------------------------------------------------------------------------------------------
# 🔍 OCR & Analysis Endpoints
# --------------------------------------------------------------------------------------------------------------


@app.post(
    "/analyze/{claim_id}",
    response_model=APIResponse[ClaimAnalysisResponse],
    summary="Run OCR on uploaded file and return extracted text",
    description="Uses Tesseract OCR to extract text from the uploaded document associated with a claim.",
)
async def analyze_claim(
    claim_id: int = Path(..., description="ID of the claim to analyze"),
    db: Session = Depends(get_db),
):
    # Step 1: Find the claim or 404
    claim = get_claim_or_404(claim_id, db)

    if not claim.document_path or not os.path.exists(claim.document_path):
        raise HTTPException(
            status_code=404,
            detail="Document file not found for this claim.",
        )

    try:
        # Step 2: Extract text via OCR (Tesseract)
        extracted_text = extract_text_from_file(claim.document_path)

        logging.info(f"[OCR_ANALYSIS] Claim ID={claim_id} OCR successful")

        # Step 3: Attempt to parse structured values from OCR output
        parsed = parse_claim_text(extracted_text)

        # Always store raw OCR results in DB, even if parsing fails
        claim.ocr_text = extracted_text  # Save the raw OCR output

        logging.info(f"Extracted OCR Text:\n{extracted_text!r}")

        # Commit OCR text alone here, so we don't lose it if parsing fails
        db.commit()
        db.refresh(claim)  # Ensures in-memory state is synced with DB

        updated_fields = []

        # Step 4: Patch parsed values into claim if found
        if parsed.get("claim_type"):
            claim.claim_type = parsed["claim_type"]
            updated_fields.append("claim_type")

        if parsed.get("amount") is not None:
            claim.amount = parsed["amount"]
            updated_fields.append("amount")

        # Step 5: If we updated parsed fields, commit again
        if updated_fields:
            db.commit()
            logging.info(
                f"[CLAIM_UPDATED_FROM_OCR] ID={claim_id} → updated fields: {', '.join(updated_fields)}"
            )

        # Optional: consider saving extracted_text to DB later
        return APIResponse(
            status="success",
            data=ClaimAnalysisResponse(
                claim_id=claim.id,
                source_file=claim.document_path,
                extracted_text=extracted_text,
            ),
        )

    except Exception as e:
        logging.error(f"OCR failed for claim {claim_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="OCR analysis failed. Please check the uploaded file format or contents.",
        )


@app.get(
    "/claims/search",
    response_model=APIResponse[List[ClaimOut]],
    dependencies=auth_stack,
    summary="Search claims by OCR text",
    description="Search the raw OCR text stored in each claim for matching content.",
)
def search_claims_by_ocr(q: str = Query(...), db: Session = Depends(get_db)):
    search_terms = q.split()
    """
    Case-insensitive search across ocr_text field.
    """

    logging.info(f"Multi-keyword search for terms: {search_terms}")

    # Choose filters depending on DB
    if is_using_postgres():
        logging.info("OR search using ILIKE for PostgreSQL")
        filters = [Claim.ocr_text.ilike(f"%{term}%") for term in search_terms]
    else:
        logging.info("OR search using LOWER + LIKE for SQLite")
        filters = [
            func.lower(Claim.ocr_text).like(f"%{term.lower()}%")
            for term in search_terms
        ]

    filter_clause = or_(*filters)

    claims = db.query(Claim).filter(filter_clause).limit(20).all()

    if not claims:
        logging.info(f"No matches found for: {search_terms}")

    logging.info(
        f"Using {engine.url.drivername} with {'ILIKE' if is_using_postgres() else 'LIKE'} for OCR search"
    )

    try:
        validated_claims = [ClaimOut.model_validate(c).model_dump() for c in claims]
        print("Successfully validated claims:", validated_claims)
    except Exception as e:
        logging.error(f"Validation error: {e}")
        raise HTTPException(status_code=500, detail="Error serializing claim data.")

    return JSONResponse(
        status_code=200,
        content={"status": "success", "data": validated_claims},
    )


@app.get(
    "/claims/{claim_id}",
    response_model=APIResponse[ClaimOut],
    summary="Get a single claim by ID",
    description="Fetches a claim from the database and returns its details.",
)
def get_single_claim(
    claim_id: int = Path(..., description="ID of the claim to retrieve"),
    db: Session = Depends(get_db),
):
    """
    Retrieves a specific claim using its ID.
    """
    claim = get_claim_or_404(claim_id, db)
    logging.info(f"Retrieved claim ID {claim_id}")
    return APIResponse(status="success", data=ClaimOut.model_validate(claim))


@app.delete(
    "/claims/{claim_id}",
    response_model=APIResponse[dict],
    summary="Delete a claim and its file",
)
def delete_claim(
    claim_id: int = Path(..., description="ID of the claim to delete"),
    db: Session = Depends(get_db),
):
    """
    Deletes a claim and its associated uploaded file from the system.
    """
    claim = get_claim_or_404(claim_id, db)

    # Try deleting the file if it exists
    delete_file_if_exists(claim.document_path)

    # Delete the DB entry
    service_delete_claim(claim, db)

    logging.info(f"[CLAIM_DELETED] ID={claim_id} deleted from DB")

    return APIResponse(status="success", data={"deleted_id": claim_id})


@app.get("/docs/examples", summary="Usage examples for the API")
def get_usage_examples():
    """
    Provides helpful examples for using the key API routes:
    /claims, /upload, /claims/{id}/status, /download/{id}, and both GET & DELETE on /claims/{id}
    """
    return {
        "description": "This route gives usage examples for the main endpoints in this API.",
        "examples": {
            "/claims": [
                {
                    "url": "/claims",
                    "explanation": "Returns the first 10 claims (default pagination).",
                },
                {
                    "url": "/claims?skip=10&limit=5",
                    "explanation": "Skips the first 10 claims and returns the next 5 (pagination).",
                },
                {
                    "url": "/claims?status=APPROVED",
                    "explanation": "Returns only claims with the status 'APPROVED'.",
                },
                {
                    "url": "/claims?claimant_name=john",
                    "explanation": "Returns claims where the claimant name contains 'john' (case-insensitive).",
                },
                {
                    "url": "/claims?status=REJECTED&claimant_name=doe",
                    "explanation": "Returns claims that are both REJECTED and contain 'doe' in the name.",
                },
            ],
            "/upload": [
                {
                    "method": "POST",
                    "url": "/upload/",
                    "content_type": "multipart/form-data",
                    "fields_required": [
                        "file (UploadFile)",
                        "claimant_name (str)",
                        "claim_type (str)",
                        "amount (float)",
                        "description (optional str)",
                    ],
                    "explanation": "Upload a file and submit a new claim. File must be one of the allowed MIME types (e.g., image/png, application/pdf) and within size limits.",
                }
            ],
            "/claims/{claim_id}/status": [
                {
                    "method": "PATCH",
                    "url": "/claims/12/status",
                    "body": {"new_status": "APPROVED"},
                    "explanation": "Updates claim #12 to 'APPROVED'. Must use one of the valid status values: PENDING, APPROVED, REJECTED, UNDER_REVIEW.",
                }
            ],
            "/download/{claim_id}": [
                {
                    "method": "GET",
                    "url": "/download/7",
                    "explanation": "Downloads the file attached to claim ID 7. Returns the file as a downloadable response with the original filename and correct MIME type.",
                }
            ],
            "/claims/{claim_id}": [
                {
                    "method": "GET",
                    "url": "/claims/5",
                    "explanation": "Retrieves the full claim details for claim ID 5. Returns status, claimant info, timestamps, and file metadata.",
                }
            ],
            "/claims/{claim_id} (DELETE)": [
                {
                    "method": "DELETE",
                    "url": "/claims/3",
                    "explanation": "Deletes claim ID 3 and its associated uploaded file (if it exists). Returns a confirmation status if successful.",
                }
            ],
        },
    }


# Run the FastAPI server if executed directly
if __name__ == "__main__":
    logging.info(
        "FastAPI server starting..."
    )  # Good place to swap to gunicorn/uvicorn for prod
    uvicorn.run(app, host="0.0.0.0", port=8000)
