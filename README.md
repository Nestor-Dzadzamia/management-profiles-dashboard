# Management Profiles Dashboard

A REST API for managing projects and their attached documents. Users create projects, invite others to collaborate, and upload pdf/docx files that are stored in object storage.

Built with FastAPI, PostgreSQL and S3-compatible storage. Deployed on AWS.

## Features

- Registration and login, with JWT-based authentication
- Create, read, update and delete projects
- Two access levels: owners can do anything, participants can edit but not delete
- Upload, download, replace and delete documents (pdf and docx)
- Invite other users to a project

## API specification

Full endpoint documentation, including request and response formats and error codes, is in [docs/api-spec.md](docs/api-spec.md).

Interactive documentation is served by the running application at `/docs`.

## Architecture

```
Client
  │
  ▼
FastAPI  ──────────►  S3 / MinIO      (document files)
  │
  ▼
PostgreSQL                            (users, projects, memberships, roles, document metadata)
```

Files themselves live in object storage; the database holds only their metadata and the key needed to find them.

### Code structure

The application is split into three layers, and each one only talks to the layer below it.

```
src/
├── main.py            application entry point
├── config.py          settings, loaded from environment variables
├── auth.py            password hashing and JWT handling
├── storage.py         object storage client
├── api/               HTTP layer: routing, request and response models
│   ├── deps.py        dependency wiring and the current-user check
│   ├── auth.py
│   ├── projects.py
│   └── documents.py
├── services/          business logic, permissions, and database access
│   ├── user.py
│   ├── project.py
│   └── document.py
└── db/                ORM models and session handling
    ├── base.py
    ├── models.py
    └── session.py
```

Each file in `services/` holds a DTO, a repository and a service together. Repositories return DTOs rather than ORM objects, so nothing above the service layer ever touches SQLAlchemy. Request and response models live alongside the endpoints that use them.

### Database

Five tables: `users`, `projects`, `documents`, `roles`, and `project_members` joining users to projects with a role.

Ownership is not a column on `projects` : it is a membership row with the owner role. Storing it in both places would mean the same fact recorded twice, with no guarantee the two agree.

Deleting a project cascades to its memberships and document rows in the database, and the application separately removes the corresponding files from object storage.

Schema changes are managed with Alembic.

## Running locally

Requires Docker and uv

```bash
git clone https://github.com/Nestor-Dzadzamia/management-profiles-dashboard.git
cd management-profiles-dashboard
cp .env.example .env
docker compose up -d --build
docker compose exec api alembic upgrade head
```

The API is then at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

This starts three containers: the API, PostgreSQL, and MinIO as a local stand-in for S3. MinIO's console is at `http://localhost:9001`.

## Tests

```bash
docker compose up -d db test-db minio
uv sync
uv run pytest
```

72 tests, in two groups.

**Unit tests** (`tests/unit/`) cover password hashing, JWT handling, and the service layer using in-memory fakes for the repository and storage. No database or network required.

**Integration tests** (`tests/integration/`) run against a real PostgreSQL instance and real object storage, exercising every endpoint through the full application stack. Each test gets a freshly created and dropped schema so tests stay independent.

Both follow the Arrange-Act-Assert pattern.

## Continuous integration

GitHub Actions runs on every push and pull request: linting and formatting with ruff, type checking with mypy, and the full test suite against containerised PostgreSQL and MinIO. `main` is protected and requires a passing build before merging.

## Deployment

Running on AWS, inside a single VPC:

- **EC2** runs the application in Docker
- **RDS** hosts PostgreSQL
- **S3** stores the documents

The database has no public address and its security group accepts connections only from the EC2 instance's security group, so it is unreachable from the internet. The instance reaches S3 through an IAM role rather than stored credentials.

The public IP is ephemeral, so the deployed URL changes whenever the instance is restarted.

## Known limitations

**Swagger cannot render the file upload forms.** The generated OpenAPI schema is correct, but Swagger UI does not yet render OpenAPI 3.1 binary fields as a file picker. The upload endpoints work normally through curl or any regular HTTP client; only the interactive documentation page is affected.

**File type validation trusts the declared content type.** Uploads are checked against the `Content-Type` the client sends. A stricter implementation would inspect the file's magic bytes, since that header can be set to anything.

**Object storage cleanup is not transactional.** PostgreSQL and S3 cannot share a transaction, so deletes remove the database row first and the stored file second. If the second step fails the file is orphaned, which wastes space but leaves nothing broken, the reverse order would leave rows pointing at files that no longer exist.
