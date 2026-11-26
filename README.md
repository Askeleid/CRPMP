# Final Project Backend

A Django and Django REST Framework backend scaffolded with a `config` project package and a `workspace` core application, OpenAPI 3 documentation via `drf-spectacular`, environment-based PostgreSQL configuration with SQLite fallback, and automated testing via `pytest`.

## Tech Stack

- **Framework:** Django 5.2, Django REST Framework
- **API Documentation:** `drf-spectacular` (OpenAPI 3 + Swagger UI)
- **Database:** PostgreSQL via `DATABASE_URL` (`python-dotenv` + `dj-database-url`), falling back to SQLite when `DATABASE_URL` is unset
- **Testing & CI:** `pytest`, `pytest-django`, `pytest-cov`, GitHub Actions

## Project Structure

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions workflow running pytest --cov
├── config/                 # Django project configuration (settings, URLs, WSGI/ASGI)
├── workspace/              # Core application (health-check endpoint, serializers, tests)
├── .env.example            # Example environment variables
├── manage.py
├── pyproject.toml          # pytest and coverage configuration
└── requirements.txt        # Python dependencies
```

## Getting Started

### 1. Activate Environment & Install Dependencies

Activate your Python/Conda environment (e.g., `conda activate pytorchGPU_env`) and install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and adjust the values as needed:

```bash
cp .env.example .env
```

- Set `DATABASE_URL` (for example, `postgres://postgres:postgres@localhost:5432/finalproject`) to connect to PostgreSQL.
- Leave `DATABASE_URL` unset to automatically fall back to local SQLite (`db.sqlite3`), which is also used in CI.

### 3. Apply Migrations & Run the Server

```bash
python manage.py migrate
python manage.py runserver
```

## API Endpoints

| Endpoint       | Description                         |
| -------------- | ----------------------------------- |
| `/api/health/` | Health-check endpoint (`status: ok`) |
| `/api/schema/` | OpenAPI 3 schema document           |
| `/api/docs/`   | Interactive Swagger UI              |

## Running Tests

Run the test suite with coverage (matching CI):

```bash
pytest --cov
```

## Continuous Integration

GitHub Actions (`.github/workflows/ci.yml`) runs `python manage.py check` and `pytest --cov` on pushes to `main` and `feat/**` branches as well as pull requests targeting `main`.
