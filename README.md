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

## System Architecture & UML Class Diagram

```mermaid
classDiagram
    class ResearchGroup {
        +UUID id
        +String name
        +Text description
        +DateTime created_at
    }
    class GroupMembership {
        +String role
        +DateTime joined_at
    }
    class Paper {
        +UUID id
        +String title
        +String authors
        +Int year
        +String doi
        +String arxiv_id
        +URL url
        +File pdf_file
        +Text abstract
    }
    class Tag {
        +String name
    }
    class ResearchTask {
        +String title
        +String status
        +Date due_date
    }
    class ExperimentLog {
        +String title
        +Text hypothesis
        +Text parameters
        +Text result_summary
        +DateTime logged_at
    }
    class Notification {
        +String message
        +Boolean is_read
        +DateTime created_at
    }
    ResearchGroup "1" --> "*" GroupMembership
    ResearchGroup "1" --> "*" Paper
    ResearchGroup "1" --> "*" ResearchTask
    Paper "*" --> "*" Tag
    Paper "1" --> "*" ExperimentLog

    %% Strategy Pattern (Behavioral)
    class CitationStrategy {
        <<interface>>
        +format(paper: Paper) str
    }
    class BibTeXStrategy {
        +format(paper: Paper) str
    }
    class APAStrategy {
        +format(paper: Paper) str
    }
    class IEEEStrategy {
        +format(paper: Paper) str
    }
    class CitationExporter {
        -CitationStrategy strategy
        +set_strategy(strategy: CitationStrategy)
        +export(paper: Paper) str
    }
    CitationStrategy <|.. BibTeXStrategy
    CitationStrategy <|.. APAStrategy
    CitationStrategy <|.. IEEEStrategy
    CitationExporter o--> CitationStrategy

    %% Adapter Pattern (Structural)
    class MetadataProvider {
        <<interface>>
        +fetch(identifier: str) dict
    }
    class ArxivAdapter {
        -ArxivClient client
        +fetch(identifier: str) dict
    }
    class CrossRefAdapter {
        -CrossRefClient client
        +fetch(identifier: str) dict
    }
    MetadataProvider <|.. ArxivAdapter
    MetadataProvider <|.. CrossRefAdapter

    %% Observer Pattern (Behavioral)
    class ResearchObserver {
        <<interface>>
        +update(event: str, payload: dict)
    }
    class InAppObserver {
        +update(event: str, payload: dict)
    }
    class EmailObserver {
        +update(event: str, payload: dict)
    }
    class EventPublisher {
        -List~ResearchObserver~ observers
        +attach(observer: ResearchObserver)
        +notify(event: str, payload: dict)
    }
    ResearchObserver <|.. InAppObserver
    ResearchObserver <|.. EmailObserver
    EventPublisher o--> ResearchObserver
```

