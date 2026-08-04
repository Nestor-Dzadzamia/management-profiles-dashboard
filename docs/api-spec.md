## Conventions

All endpoints except `POST /auth` and `POST /login` require `Authorization: Bearer <token>`.

JWT is HS256 and lasts 1 hour. IDs are integers. Timestamps are ISO 8601 UTC.

Responses are flat. Related entities are referenced by ID, never embedded.

Errors return `{"detail": "..."}`. Validation failures use FastAPI's default 422 shape.

| Code | Meaning |
|---|---|
| 401 | Missing, expired or invalid token |
| 403 | Is a member of the project, but not allowed to do this |
| 404 | Doesn't exist, or the caller has no access |
| 409 | Duplicate login, or user is already a member |
| 413 | File too large |
| 415 | Unsupported file type |
| 422 | Body failed validation |
| 500 | Server error |

A caller with no access to a project gets 404 rather than 403, so the API doesn't reveal that the project exists. 403 is only used when the caller is a member but lacks the required role.

## Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/auth` | Create user |
| POST | `/login` | Log in, returns JWT |
| POST | `/projects` | Create project, caller becomes owner |
| GET | `/projects` | List projects the caller can access |
| GET | `/project/{project_id}/info` | Project details |
| PUT | `/project/{project_id}/info` | Update name and description |
| DELETE | `/project/{project_id}` | Delete project and its documents, owner only |
| POST | `/project/{project_id}/invite` | Grant a user participant access, owner only |
| GET | `/project/{project_id}/documents` | List the project's documents |
| POST | `/project/{project_id}/documents` | Upload document(s) |
| GET | `/document/{document_id}` | Download document |
| PUT | `/document/{document_id}` | Replace document |
| DELETE | `/document/{document_id}` | Delete document |

---

### POST /auth

In:

```json
{"login": "nestor.dzadzamia", "password": "...", "repeat_password": "..."}
```

Out, 201:

```json
{"id": 1, "login": "nestor.dzadzamia", "created_at": "2026-08-04T10:00:00Z"}
```

Errors: 409 if the login is taken, 422 if the passwords differ or constraints fail.

### POST /login

In:

```json
{"login": "nestor.dzadzamia", "password": "..."}
```

Out, 200:

```json
{"access_token": "eyJ...", "token_type": "bearer", "expires_in": 3600}
```

Errors: 401, 422. The 401 is identical whether the login is unknown or the password is wrong.

---

### POST /projects

In:

```json
{"name": "Website redesign", "description": "Q3 refresh"}
```

Out, 201:

```json
{
  "id": 7,
  "name": "Website redesign",
  "description": "Q3 refresh",
  "owner_id": 1,
  "role": "owner",
  "created_at": "2026-08-04T10:05:00Z",
  "updated_at": "2026-08-04T10:05:00Z"
}
```

`role` is the calling user's role in this project.

Errors: 401, 422.

### GET /projects

Out, 200:

```json
[
  {
    "id": 7,
    "name": "Website redesign",
    "description": "Q3 refresh",
    "owner_id": 1,
    "role": "owner",
    "document_ids": [42, 43],
    "created_at": "2026-08-04T10:05:00Z",
    "updated_at": "2026-08-04T10:05:00Z"
  }
]
```

Documents are referenced by ID rather than embedded. Full document metadata comes from `GET /project/{id}/documents`.

Errors: 401.

### GET /project/{project_id}/info

Out, 200: the project object without `document_ids`.

Errors: 401, 404.

### PUT /project/{project_id}/info

In:

```json
{"name": "Website redesign", "description": "Q3 and Q4 refresh"}
```

Both fields required. Owner and participant can both edit.

Out, 200: the updated project.

Errors: 401, 404, 422.

### DELETE /project/{project_id}

Owner only. Deletes the memberships, the document rows and the stored files.

Out, 204.

Errors: 401, 403, 404.

### POST /project/{project_id}/invite?user={login}

Owner only. The invited user joins as a participant.

Out, 201:

```json
{"project_id": 7, "user_id": 2, "role": "participant", "joined_at": "2026-08-04T12:30:00Z"}
```

Errors: 401, 403, 404 (project or target user), 409 if already a member.

---

### GET /project/{project_id}/documents

Out, 200:

```json
[
  {
    "id": 42,
    "project_id": 7,
    "filename": "brief.pdf",
    "content_type": "application/pdf",
    "size_bytes": 248113,
    "uploaded_by_id": 1,
    "created_at": "2026-08-04T11:00:00Z",
    "updated_at": "2026-08-04T11:00:00Z"
  }
]
```

Errors: 401, 404.

### POST /project/{project_id}/documents

`multipart/form-data` with a repeated `files` field, so one request can carry several documents. pdf and docx only, 25 MB per file. If any file fails validation, none are stored.

Out, 201: an array of the created document objects.

Errors: 401, 404, 413, 415, 422.

### GET /document/{document_id}

Returns the file itself, streamed from object storage. The only endpoint that doesn't return JSON.

Out, 200, with `Content-Type` set to the stored type and `Content-Disposition: attachment; filename="brief.pdf"`.

Errors: 401, 404.

### PUT /document/{document_id}

`multipart/form-data` with a single `file` field. Same validation as upload. The document ID is preserved; filename, size, content type and `updated_at` are refreshed.

Out, 200: the updated document object.

Errors: 401, 404, 413, 415, 422.

### DELETE /document/{document_id}

Owner and participant both allowed.

Out, 204.

Errors: 401, 404.