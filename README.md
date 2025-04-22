# Insurance Claim AI (WIP)

A FastAPI-based backend for AI-assisted insurance claim processing.  
Currently transitioning from **SQLite** to **PostgreSQL**, with core backend APIs already in place and the frontend development yet to begin.

---

## Tech Stack

- **Python 3.10+**
- **FastAPI** – Modern, async web framework
- **PostgreSQL** – Current DB in use (via `psycopg2`)
- **SQLAlchemy** – ORM
- **Uvicorn** – ASGI server
- **Tesseract OCR** – For text extraction (planned or in progress)
- **Pydantic** – Data validation
- **Pre-commit** (black, isort) – Formatting and linting

---

## Project Structure

```plaintext
.
├── auth.py                # Handles authentication logic
├── create_tables.py       # DB schema setup and table generation
├── database.py            # Database connection using PostgreSQL (via psycopg2)
├── models.py              # SQLAlchemy models
├── main.py                # FastAPI application entrypoint
├── rate_limiter.py        # Request limiting (WIP)
├── schemas.py             # Pydantic request/response schemas
├── services.py            # Business logic for claims
├── utils.py               # Helpers (file handling, OCR, etc.)
├── .env                   # Environment variables (not committed)
├── .gitignore             # Ignores venv, .env, .db, etc.
└── uploads/               # Uploaded files
```

---

## Setup Instructions (PostgreSQL)

1. Clone the repo:
    ```bash
    git clone https://github.com/Doppler-stack/insurance-claim-ai.git
    cd insurance-claim-ai
    ```

2. Create and activate virtual environment:
    ```bash
    python -m venv venv
    source venv/Scripts/activate  # Windows
    ```

3. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

4. Set up your PostgreSQL `.env` with variables like:
    ```env
    DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/your_db
    ```

5. Run the app:
    ```bash
    uvicorn main:app --reload
    ```

6. Access the docs:
    - [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🔧 In Progress

- PostgreSQL migration underway (psycopg2 already configured)
- OCR data extraction
- AI logic for fraud detection
- Frontend (Next.js or React) not yet started

---

## Code Style

Run formatting tools:

```bash
isort .
black .
```

Install pre-commit hooks:

```bash
pre-commit install
```

---

## Frontend (Planned)

To be built in a future phase using either **Next.js** or **React**, deployed via **Vercel**.

---

## 📌 Status

| Feature        | Status      |
|----------------|-------------|
| Backend API    | ✅ Complete |
| OCR/AI Layer   | ⚠️ WIP      |
| PostgreSQL     | 🟡 In Progress |
| Frontend UI    | ❌ Not Started |

---

## 🤝 Contributions

Open to suggestions, pull requests, and community feedback as this project evolves.

---

## License

MIT License
