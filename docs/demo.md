# Demo requests

Set the host once. We need this since EC2 gets new IP every restart.

```bash
HOST=http://REPLACE_WITH_EC2_IP:8000
```

Local instead:

```bash
HOST=http://localhost:8000
```

---

## 1. Health

Proves the service is up before anything else.

```bash
curl -s $HOST/health
```

Expect `{"status":"ok"}`

---

## 2. Register the owner

```bash
curl -s -X POST $HOST/auth \
  -H "Content-Type: application/json" \
  -d '{"login":"nestor","password":"some_random_password","repeat_password":"some_random_password"}'
```

Expect **201**. Note there is no password or hash in the response.

### Duplicate login is rejected

```bash
curl -s -w "\n%{http_code}\n" -X POST $HOST/auth \
  -H "Content-Type: application/json" \
  -d '{"login":"nestor","password":"some_random_password","repeat_password":"some_random_password"}'
```

Expect **409**

### Mismatched passwords are rejected before any code runs

```bash
curl -s -w "\n%{http_code}\n" -X POST $HOST/auth \
  -H "Content-Type: application/json" \
  -d '{"login":"someone","password":"some_random_password","repeat_password":"different_password"}'
```

Expect **422**, validated by the schema rather than by hand.

---

## 3. Log in

```bash
curl -s -X POST $HOST/login \
  -H "Content-Type: application/json" \
  -d '{"login":"nestor","password":"some_random_password"}'
```

Copy the token:

```bash
OWNER="Authorization: Bearer PASTE_TOKEN_HERE"
```

### Wrong password and unknown user give the same answer

```bash
curl -s -w "\n%{http_code}\n" -X POST $HOST/login \
  -H "Content-Type: application/json" \
  -d '{"login":"nestor","password":"wrong_password"}'

curl -s -w "\n%{http_code}\n" -X POST $HOST/login \
  -H "Content-Type: application/json" \
  -d '{"login":"does_not_exist","password":"some_random_password"}'
```

Both **401**, identical. The endpoint cannot be used to discover which accounts exist.

---

## 4. Authentication is required

```bash
curl -s -w "\n%{http_code}\n" $HOST/projects
```

Expect **401** with no token.

---

## 5. Create a project

```bash
curl -s -X POST $HOST/projects \
  -H "$OWNER" \
  -H "Content-Type: application/json" \
  -d '{"name":"Website redesign","description":"Q3 refresh"}'
```

Expect **201**, `role: "owner"`. The creator becomes the owner automatically.

---

## 6. List and read

```bash
curl -s $HOST/projects -H "$OWNER"
```

Flat response, related entities referenced by id.

```bash
curl -s $HOST/project/1/info -H "$OWNER"
```

---

## 7. Update

```bash
curl -s -X PUT $HOST/project/1/info \
  -H "$OWNER" \
  -H "Content-Type: application/json" \
  -d '{"name":"Website redesign v2","description":"Q3 and Q4"}'
```

Expect **200**, with `updated_at` later than `created_at`.

---

## 8. Upload a document

```bash
printf '%%PDF-1.4\ndemo file\n%%%%EOF' > /tmp/brief.pdf

curl -s -X POST $HOST/project/1/documents \
  -H "$OWNER" \
  -F "files=@/tmp/brief.pdf;type=application/pdf"
```

Expect **201**. Note `s3_key` is absent from the response, it is internal.

### Only pdf and docx are accepted

```bash
echo "hello" > /tmp/notes.txt

curl -s -w "\n%{http_code}\n" -X POST $HOST/project/1/documents \
  -H "$OWNER" \
  -F "files=@/tmp/notes.txt;type=text/plain"
```

Expect **415**

### Several files in one request

```bash
printf '%%PDF-1.4\none\n%%%%EOF' > /tmp/one.pdf
printf '%%PDF-1.4\ntwo\n%%%%EOF' > /tmp/two.pdf

curl -s -X POST $HOST/project/1/documents \
  -H "$OWNER" \
  -F "files=@/tmp/one.pdf;type=application/pdf" \
  -F "files=@/tmp/two.pdf;type=application/pdf"
```

---

## 9. List and download

```bash
curl -s $HOST/project/1/documents -H "$OWNER"
```

```bash
curl -s $HOST/document/1 -H "$OWNER"
```

Returns the file itself. The only endpoint that is not JSON.

```bash
curl -s $HOST/projects -H "$OWNER"
```

The project now carries `document_ids`.

---

## 10. Replace a document

```bash
printf '%%PDF-1.4\nreplaced contents\n%%%%EOF' > /tmp/updated.pdf

curl -s -X PUT $HOST/document/1 \
  -H "$OWNER" \
  -F "file=@/tmp/updated.pdf;type=application/pdf"
```

Same id, new filename and size. The previous object is removed from storage.

---

## 11. A second user, and permissions

```bash
curl -s -X POST $HOST/auth \
  -H "Content-Type: application/json" \
  -d '{"login":"giorgi","password":"some_random_password","repeat_password":"some_random_password"}'

curl -s -X POST $HOST/login \
  -H "Content-Type: application/json" \
  -d '{"login":"giorgi","password":"some_random_password"}'
```

```bash
GUEST="Authorization: Bearer PASTE_SECOND_TOKEN_HERE"
```

### A stranger gets 404, not 403

```bash
curl -s -w "\n%{http_code}\n" $HOST/project/1/info -H "$GUEST"
```

Expect **404**. A 403 would confirm the project exists to someone with no right to know that.

```bash
curl -s $HOST/projects -H "$GUEST"
```

Empty list.

---

## 12. Invite

```bash
curl -s -X POST "$HOST/project/1/invite?user=giorgi" -H "$OWNER"
```

Expect **201**, role participant.

```bash
curl -s $HOST/project/1/info -H "$GUEST"
```

Now **200**, showing `role: "participant"`.

### Inviting twice conflicts

```bash
curl -s -w "\n%{http_code}\n" -X POST "$HOST/project/1/invite?user=giorgi" -H "$OWNER"
```

Expect **409**

### Inviting an unknown user

```bash
curl -s -w "\n%{http_code}\n" -X POST "$HOST/project/1/invite?user=nobody" -H "$OWNER"
```

Expect **404**

---

## 13. Participant permissions

Can edit:

```bash
curl -s -w "\n%{http_code}\n" -X PUT $HOST/project/1/info \
  -H "$GUEST" \
  -H "Content-Type: application/json" \
  -d '{"name":"Edited by the participant","description":"still fine"}'
```

Expect **200**

Can upload:

```bash
curl -s -w "\n%{http_code}\n" -X POST $HOST/project/1/documents \
  -H "$GUEST" \
  -F "files=@/tmp/brief.pdf;type=application/pdf"
```

Expect **201**

Cannot delete the project:

```bash
curl -s -w "\n%{http_code}\n" -X DELETE $HOST/project/1 -H "$GUEST"
```

Expect **403**. This is the one case where 403 is right, the caller is a member, just not the owner.

Cannot invite:

```bash
curl -s -w "\n%{http_code}\n" -X POST "$HOST/project/1/invite?user=nestor" -H "$GUEST"
```

Expect **403**

---

## 14. Delete a document

```bash
curl -s -w "\n%{http_code}\n" -X DELETE $HOST/document/1 -H "$OWNER"
```

Expect **204**. The row goes first, then the stored file.

---

## 15. Delete the project

```bash
curl -s -w "\n%{http_code}\n" -X DELETE $HOST/project/1 -H "$OWNER"
```

Expect **204**.

```bash
curl -s $HOST/projects -H "$OWNER"
```

Empty. The documents went with it, both the database rows, by cascade, and the files in storage.

---

## Notes for the demo

- `-w "\n%{http_code}\n"` prints the status code, which matters for the error cases
- Swagger at `$HOST/docs` covers everything except the file uploads, which it cannot render
- Have the S3 console open to show objects appearing and disappearing during steps 8, 14 and 15