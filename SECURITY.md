# Security Policy 🔒

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting Security Issues

We take the security of this project seriously. If you discover a security vulnerability or credential leak issue, please do not open a public GitHub issue.

Please report security issues privately to the project maintainer.

## Local Token & Credential Safety

- **Never commit `credentials.json`, `token.json`, or `.env` to any git repository.**
- All token files and SQLite database stores are included in `.gitignore` by default.
- Always use restricted OAuth scopes when configuring Google Cloud Console applications.
