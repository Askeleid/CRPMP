# Collaborative Research Paper Management Platform (CRPMP)

A Django and Django REST Framework platform for collaborative research groups to manage papers, tasks, experiment logs, citations, external metadata imports, and notifications — documented with OpenAPI 3 / Swagger UI (`drf-spectacular`) and backed by unit, API, mocked, and Selenium end-to-end tests.

## Tech Stack

- **Framework:** Django 5.2, Django REST Framework, Bootstrap 5 (CDN)
- **API Documentation:** `drf-spectacular` (OpenAPI 3 + Swagger UI)
- **Database:** PostgreSQL via `DATABASE_URL` (`python-dotenv` + `dj-database-url`), falling back to SQLite when `DATABASE_URL` is unset
- **Testing & CI:** `pytest`, `pytest-django`, `pytest-cov`, `selenium` (headless Chrome), GitHub Actions

## Project Structure

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml                       # CI workflow running checks, OpenAPI validation, and pytest
├── config/                              # Django project configuration (settings, URLs, WSGI/ASGI)
├── workspace/
│   ├── migrations/                      # Database migrations (groups, papers, tasks, logs, notifications)
│   ├── patterns/
│   │   ├── citations.py                 # Strategy Pattern (BibTeX, APA, IEEE)
│   │   ├── metadata.py                  # Adapter Pattern (arXiv, CrossRef)
│   │   └── observers.py                 # Observer Pattern (InApp, Email)
│   ├── templates/                       # Bootstrap 5 templates (auth, dashboard, group & paper detail)
│   ├── tests/
│   │   ├── test_health.py
│   │   ├── test_groups_papers.py
│   │   ├── test_tasks_logs.py
│   │   ├── test_citation_strategy.py
│   │   ├── test_metadata_adapter.py
│   │   ├── test_observer_notifications.py
│   │   └── test_selenium_e2e.py         # End-to-end browser tests with headless Chrome
│   ├── admin.py
│   ├── api_urls.py                      # DRF router endpoints (/api/...)
│   ├── api_views.py                     # DRF ViewSets & @extend_schema annotations
│   ├── context_processors.py            # Unread notification count & recent alerts
│   ├── forms.py
│   ├── models.py
│   ├── permissions.py                   # IsGroupMember & IsNotificationRecipient
│   ├── serializers.py
│   ├── services.py                      # Domain services & notification triggers
│   ├── urls.py                          # Web UI routes
│   └── views.py                         # Web UI views
├── .env.example                         # Example environment variables
├── manage.py
├── pyproject.toml                       # pytest and coverage configuration
└── requirements.txt                     # Python dependencies (including selenium)
```

## Design Patterns Summary

- **Strategy Pattern** (`workspace/patterns/citations.py`): `CitationStrategy` interface with concrete `BibTeXStrategy`, `APAStrategy`, and `IEEEStrategy` implementations, switched at runtime via `CitationExporter` and resolved by `get_citation_strategy()`.
- **Adapter Pattern** (`workspace/patterns/metadata.py`): `MetadataProvider` interface with `ArxivAdapter` (Atom XML) and `CrossRefAdapter` (REST JSON), normalizing external API responses into a unified paper metadata dictionary via `get_metadata_adapter()`.
- **Observer Pattern** (`workspace/patterns/observers.py`): `ResearchObserver` interface with `InAppObserver` and `EmailObserver`, managed by `EventPublisher` (`attach()`, `detach()`, `notify()`) and `get_default_publisher()` on paper and task events.

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

## API Endpoints & Swagger UI

Once the server is running locally, access the interactive **Swagger UI** at:

- **Swagger UI:** `http://127.0.0.1:8000/api/docs/`
- **OpenAPI 3 Schema:** `http://127.0.0.1:8000/api/schema/`

| Endpoint                               | Description                                              |
| -------------------------------------- | -------------------------------------------------------- |
| `/api/health/`                         | Health-check endpoint (`status: ok`)                     |
| `/api/schema/`                         | OpenAPI 3 schema document                                |
| `/api/docs/`                           | Interactive Swagger UI                                   |
| `/api/groups/`                         | CRUD for research groups (creator auto-added as `ADMIN`) |
| `/api/papers/`                         | CRUD for papers (`?search=`, `?tag=`, `?year=`, `?group=`) |
| `/api/papers/{id}/cite/`               | Export citation (`?format=bibtex\|apa\|ieee`)            |
| `/api/papers/import-metadata/`         | Import paper from arXiv or CrossRef metadata             |
| `/api/tasks/`                          | CRUD for research tasks (`?group=`, `?status=`)          |
| `/api/experiment-logs/`                | CRUD for paper experiment logs (`?paper=`)               |
| `/api/notifications/`                  | List/retrieve in-app notifications                       |
| `/api/notifications/{id}/mark-read/`   | Mark a notification as read (`POST`)                     |

## Running Tests

Run the full test suite (unit, mocked adapter/observer, DRF API, and headless Chrome Selenium E2E tests) with coverage:

```bash
python -m pytest -p no:cacheprovider --cov
```

Validate the OpenAPI 3 schema:

```bash
python manage.py spectacular --validate
```

## Continuous Integration

GitHub Actions (`.github/workflows/ci.yml`) runs `python manage.py check`, `python manage.py spectacular --validate`, and `python -m pytest -p no:cacheprovider --cov` on pushes to `main`, `feat/**`, and `test/**` branches as well as pull requests targeting `main`.

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

