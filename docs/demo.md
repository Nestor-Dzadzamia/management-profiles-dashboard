# Demo

Run through Swagger at `<host>/docs`. (either localhost or AWS EC2)

**Before starting**, reset to an empty database. the ids below assume a fresh start:

```bash
docker compose -f docker-compose.prod.yml exec api alembic downgrade base
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
aws s3 rm s3://dashboard-documents-nestor-2026 --recursive
```

Have two small pdf files ready to upload.

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

**201.** No password or hash in the response. the response schema does not include them, so they cannot leak.

### The same login twice

Execute the identical request again.

**409**

### Passwords that do not match

```json
{
  "login": "someone",
  "password": "some_random_password",
  "repeat_password": "different_password"
}
```

**422.** Rejected by the schema before any application code runs.

---

## 3. Log in

`POST /login`

```json
{
  "login": "nestor",
  "password": "some_random_password"
}
```

**200.** Copy `access_token`.

Click **Authorize** at the top right, paste the token, Authorize, Close.

### Wrong password

```json
{
  "login": "nestor",
  "password": "wrong_password"
}
```

**401**

### A user that does not exist

```json
{
  "login": "does_not_exist",
  "password": "some_random_password"
}
```

**401**, byte-for-byte identical to the previous response. The endpoint cannot be used to find out which accounts exist.

---

## 4. Create a project

`POST /projects`

```json
{
  "name": "Nestor's Project",
  "description": "Some random description"
}
```

**201**, with `role: "owner"`. The creator becomes the owner automatically, in the same transaction.

---

## 5. Read

`GET /projects`

A flat array. Related entities appear as ids, not nested objects.

`GET /project/{project_id}/info` with `project_id` = **1**

---

## 6. Update

`PUT /project/{project_id}/info`, `project_id` = **1**

```json
{
  "name": "Website redesign v2",
  "description": "Q3 and Q4"
}
```

**200**, and `updated_at` is now later than `created_at`. the database sets it, not the application.

---

## 7. Upload a document

`POST /project/{project_id}/documents`, `project_id` = **1**

Choose a pdf file → **Execute**

**201.** Note `s3_key` is absent. it exists on the internal object but is not part of the response schema.

Show the object appearing in the S3 console under `projects/1/`. The stored name is generated, not the uploaded filename, so a hostile filename cannot become a storage path.

### A file type that is not allowed

Upload a `.txt` file.

**415**

---

## 8. List and download

`GET /project/{project_id}/documents`, `project_id` = **1**

`GET /document/{document_id}`, `document_id` = **1**

Returns the file itself. The only endpoint that does not return JSON.

`GET /projects`

The project now carries `document_ids`.

---

## 9. Replace a document

`PUT /document/{document_id}`, `document_id` = **1**

Choose a different pdf → **Execute**

**200.** Same id, new filename and size. In S3 the old object is gone and a new one has appeared. the upload happens before the delete, so a failure midway leaves the original intact.

---

## 10. A second user

Open a **private browser window** so both sessions can be held at once, and use Swagger there for the participant.

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

### A stranger cannot see the project

`GET /project/{project_id}/info`, `project_id` = **1**

**404**, not 403. A 403 would confirm the project exists to somebody with no right to know that.

`GET /projects`

Empty array.

---

## 11. Invite

Back in the **owner's window**.

`POST /project/{project_id}/invite`, `project_id` = **1**, `user` = **giorgi**

**201**, role participant.

In the **participant's window**: `GET /project/{project_id}/info` → now **200**, showing `role: "participant"`.

### Inviting the same person twice

**409**

### Inviting somebody who does not exist

`user` = **nobody** → **404**

---

## 12. What a participant may and may not do

All in the participant's window.

**Can edit**. `PUT /project/1/info`

```json
{
  "name": "Edited by the participant",
  "description": "participants can modify"
}
```

**200**

**Can upload**. `POST /project/1/documents` with a pdf → **201**

**Cannot delete the project**. `DELETE /project/1` → **403**

This is the one place 403 is correct: the caller is a member, just not the owner. Everywhere else a missing permission returns 404.

**Cannot invite**. `POST /project/1/invite`, `user` = **nestor** → **403**

---

## 13. Delete a document

Owner's window. `DELETE /document/{document_id}`, `document_id` = **1**

**204.** The database row is removed first, then the stored file. There is no transaction spanning Postgres and S3, so the order is chosen deliberately: a failure leaves an orphaned file, which wastes space, rather than a row pointing at a file that is gone, which breaks downloads.

Show it disappearing from S3.

---

## 14. Delete the project

`DELETE /project/{project_id}`, `project_id` = **1**

**204**

`GET /projects` → empty.

The documents went with it. Their database rows by foreign key cascade, and their files by an explicit cleanup step in the delete handler.

Show `projects/1/` is now empty in S3.

---

## Points worth making as they come up

**Flat responses.** Everything is one level deep, related entities referenced by id.

**404 rather than 403** for callers with no access, so the API does not confirm that resources exist to people who should not know.

**Identical 401** for unknown login and wrong password.

**Ownership is not a column** on projects. it is a membership row with the owner role. Storing it twice would let the two copies disagree.

**Cascades** handle the database side of deletion; storage cleanup is explicit because the two systems cannot share a transaction.