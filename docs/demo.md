# Demo walkthrough

Run through Swagger at `<host>/docs`. Every body below is copy-paste.

**Before starting**, reset to an empty database: the ids assume a fresh start:

```bash
docker compose -f docker-compose.prod.yml exec api alembic downgrade base
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
aws s3 rm s3://dashboard-documents-nestor-2026 --recursive
```

Have two small pdf files and one txt file ready.

Open Swagger a second time in a **private window**: that holds the participant's session, since Swagger stores one token at a time.

---

## 1. Health

`GET /health` → **Execute**

```json
{"status": "ok"}
```

---

## 2. Register the owner

`POST /auth`

```json
{
  "login": "nestor",
  "password": "some_random_password",
  "repeat_password": "some_random_password"
}
```

**201.** No password or hash in the response: the response schema doesn't include them, so they can't leak.

### The same login twice

Execute the identical request again.

**409**

### Passwords that don't match

```json
{
  "login": "someone",
  "password": "some_random_password",
  "repeat_password": "different_password"
}
```

**422.** Rejected by the schema before any application code runs.

### Login too short

```json
{
  "login": "ab",
  "password": "some_random_password",
  "repeat_password": "some_random_password"
}
```

**422**

---

## 3. Log in

`POST /login`

```json
{
  "login": "nestor",
  "password": "some_random_password"
}
```

**200.** Copy `access_token`, click **Authorize**, paste, Authorize, Close.

### Wrong password

```json
{
  "login": "nestor",
  "password": "wrong_password"
}
```

**401**

### A user that doesn't exist

```json
{
  "login": "does_not_exist",
  "password": "some_random_password"
}
```

**401**, identical to the previous response. The endpoint can't be used to discover which accounts exist.

---

## 4. Authentication is required

Click **Authorize → Logout**, then `GET /projects` → **401**

Log back in and re-authorize before continuing.

---

## 5. Create a project

`POST /projects`

```json
{
  "name": "Website redesign",
  "description": "Q3 refresh"
}
```

**201**, `role: "owner"`, `id: 1`. The creator becomes owner automatically, in the same transaction.

### Empty name

```json
{
  "name": "",
  "description": "should fail"
}
```

**422**

---

## 6. Read

`GET /projects`

A flat array. Related entities appear as ids, not nested objects.

`GET /project/{project_id}/info` with **1**

### A project that doesn't exist

`GET /project/{project_id}/info` with **999**

**404**

---

## 7. Update

`PUT /project/{project_id}/info`, id **1**

```json
{
  "name": "Website redesign v2",
  "description": "Q3 and Q4"
}
```

**200**, and `updated_at` is now later than `created_at`: the database sets it, not the application.

---

## 8. Upload a document

`POST /project/{project_id}/documents`, id **1**

Choose a pdf → **Execute**

**201.** Note `s3_key` is absent: it exists internally but isn't part of the response schema.

**Show S3**: object under `projects/1/`, with a generated name rather than the uploaded filename.

### A type that isn't allowed

Upload the txt file.

**415**

### Uploading to a project that doesn't exist

`POST /project/999/documents` with a pdf

**404**

---

## 9. List and download

`GET /project/{project_id}/documents`, id **1**

`GET /document/{document_id}`, id **1**

Returns the file itself. The only endpoint that isn't JSON.

`GET /projects`

The project now carries `document_ids`.

### A document that doesn't exist

`GET /document/{document_id}` with **999**

**404**

---

## 10. Replace a document

`PUT /document/{document_id}`, id **1**

Choose the second pdf → **Execute**

**200.** Same id, new filename and size.

**Show S3**: the old object is gone, a new one has appeared. The upload happens before the delete, so a failure midway leaves the original intact.

### Replacing with a disallowed type

Upload the txt file to the same endpoint.

**415**

---

## 11. A second user

In the **private window**.

`POST /auth`

```json
{
  "login": "giorgi",
  "password": "some_random_password",
  "repeat_password": "some_random_password"
}
```

`POST /login`

```json
{
  "login": "giorgi",
  "password": "some_random_password"
}
```

Authorize with this token in the private window.

### A stranger can't see the project

`GET /project/{project_id}/info`, id **1**

**404**, not 403. A 403 would confirm the project exists to someone with no right to know that. Same response as for a project that genuinely doesn't exist: deliberately indistinguishable.

`GET /projects` → empty array

### A stranger can't reach its documents either

`GET /project/1/documents` → **404**

`GET /document/1` → **404**

`DELETE /document/1` → **404**

---

## 12. Invite

Back in the **owner's window**.

`POST /project/{project_id}/invite`, id **1**, `user` = **giorgi**

**201**, role participant.

In the **participant's window**: `GET /project/1/info` → now **200**, `role: "participant"`.

### Inviting the same person twice

**409**

### Inviting someone who doesn't exist

`user` = **nobody** → **404**

### Inviting to a project that doesn't exist

`POST /project/999/invite`, `user` = **giorgi** → **404**

---

## 13. What a participant may and may not do

All in the **participant's window**.

**Can read**: `GET /project/1/documents` → **200**

**Can download**: `GET /document/1` → **200**

**Can edit**: `PUT /project/1/info`

```json
{
  "name": "Edited by the participant",
  "description": "participants can modify"
}
```

**200**

**Can upload**: `POST /project/1/documents` with a pdf → **201**

**Cannot delete the project**: `DELETE /project/1` → **403**

The one place 403 is correct: the caller is a member, just not the owner. Everywhere else a missing permission returns 404.

**Cannot invite**: `POST /project/1/invite`, `user` = **nestor** → **403**

---

## 14. Delete a document

Owner's window. `DELETE /document/{document_id}`, id **1**

**204.** The database row goes first, then the stored file. There's no transaction spanning Postgres and S3, so the order is deliberate: a failure leaves an orphaned file, which wastes space, rather than a row pointing at a file that's gone, which breaks downloads.

**Show S3**: object gone.

`GET /document/1` → **404**

---

## 15. Delete the project

`DELETE /project/{project_id}`, id **1**

**204**

`GET /projects` → empty

The documents went with it: rows by foreign key cascade, files by an explicit cleanup step.

**Show S3**: `projects/1/` is empty.

---

## Points worth making as they come up

**Flat responses.** One level deep, related entities by id.

**404 rather than 403** for anyone without access, so the API doesn't confirm what exists to people who shouldn't know. 403 appears once: a member with the wrong role.

**Identical 401** for unknown login and wrong password.

**Ownership isn't a column** on projects: it's a membership row with the owner role. Storing it twice would let the copies disagree.

**Storage keys are generated**, never derived from the filename. Otherwise `../../etc/passwd.pdf` becomes a path.

**Cascades handle the database** on delete; storage cleanup is explicit, because the two systems can't share a transaction.—
