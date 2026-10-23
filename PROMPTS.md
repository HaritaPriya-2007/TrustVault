# AI Prompt and Debugging Log — TrustVault

## Entry 1 — 2026-10-23 — Django project validation

**Prompt / assistance used:** Help me verify the Django project setup and run automated tests.

**Output:** Ran `python manage.py check` and `python manage.py test`.

**Result:** Django reported no system-check issues. All 23 discovered tests passed.

**Change made:** Recorded the successful validation result.

**Fixing commit:** Initial verification; no dedicated fixing commit.

## Entry 2 — 2026-10-23 — Authorization and role-based access

**Prompt / assistance used:** Help debug why the audit log returns HTTP 403 for a logged-in user.

**Output:** Inspected the audit view's role check and the logged-in user's role.

**Error / observation:** The logged-in account had the VIEWER role, while the audit page required ADMIN.

**Change made:** Identified that the 403 response was expected for the viewer account. The administrator account must be used to access the audit log.

**Security decision:** Keep the server-side administrator check. Do not remove authorization to make the page accessible.

**Fixing commit:** No dedicated fixing commit recorded yet.

## Entry 3 — 2026-10-23 — Document authorization

**Prompt / assistance used:** Review document access-control behavior and tests for unauthorized access.

**Output:** Discussed checking document ownership and active grants on the server.

**Security requirement:** A user must not access another user's document without appropriate permission. Revoked grants must no longer authorize access.

**Change made:** Verification and any additional fixes must be documented after reviewing the actual permission code and tests.

**Fixing commit:** To be added after the relevant code is verified and committed.

## Entry 4 — 2026-10-23 — Audit trail integrity

**Prompt / assistance used:** Help debug audit event hashing and hash-chain verification tests.

**Output:** Reviewed the event hash calculation, previous-event hash linkage, and chain verification approach.

**Error / observation:** Earlier audit tests exposed problems with event hash generation and persistence.

**Change made:** The audit model's save logic was reviewed and corrected during debugging. The final integrity behavior must be confirmed by running the tests.

**Security requirement:** Detect changes to recorded audit details and broken hash links.

**Fixing commit:** To be added after identifying the actual fixing commit.

## Entry 5 — 2026-10-23 — Git repository and sensitive files

**Prompt / assistance used:** Help prepare TrustVault for a public Git repository without exposing private files.

**Output:** Reviewed Git status and ignore rules for the local database, uploaded documents, virtual environment, and environment files.

**Observation:** `db.sqlite3` and `private_documents/` are configured to be ignored by Git.

**Change made:** Prepared project documentation and a requirements file. Staged files must still be reviewed before committing.

**Security requirement:** Never publish real credentials, API keys, the local database, or private uploaded documents.

**Fixing commit:** To be added after the relevant changes are committed.
