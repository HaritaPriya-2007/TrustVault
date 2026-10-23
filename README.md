# TrustVault

Secure document sharing with role-based access control and an audit trail.

## Features

- User authentication and roles
- Document upload and download
- Per-document access grants
- Sharing and access revocation
- Audit events with hash-chain verification
- Admin-only audit log dashboard

## Technology Stack

- Python
- Django
- SQLite for local development

## Local Setup

1. Clone the repository.
2. Create and activate a Python virtual environment.
3. Install dependencies from `requirements.txt`.
4. Run database migrations.
5. Create an administrator account.
6. Start the development server.

## Security

- Private documents must not be committed to Git.
- Authorization is checked server-side.
- Audit-log access is restricted to administrators.

## Testing

Run the automated tests:

```bash
python manage.py test
```

## Deployment

Deployment URL: TODO

## Demo Accounts

Add the deployed demo account usernames and passwords before submission.
Do not publish personal or reused passwords.

## Known Limitations

- Public deployment is not yet documented.
- Security tests and deployment checks must be verified before submission.
