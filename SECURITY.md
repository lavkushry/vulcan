# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in Vulcan, please report it responsibly.

### Responsible Disclosure

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Instead, send an email to:

📧 **security@vulcan-project.dev**

Include the following in your report:

- A description of the vulnerability
- Steps to reproduce the issue
- The potential impact
- Any suggested fixes (if applicable)

### What to Expect

- **Acknowledgment**: We will acknowledge your report within **48 hours**.
- **Assessment**: We will investigate and provide an initial assessment within **5 business days**.
- **Resolution**: We aim to release a fix within **30 days** of confirming the vulnerability, depending on complexity.
- **Credit**: With your permission, we will credit you in the release notes.

## Security Practices

### Demo Credentials and SSH Keys

> **All demo SSH keys committed before this release have been rotated and are no longer valid.**

Any SSH keys, API tokens, or credentials found in the repository's Git history from early development are **expired and non-functional**. They were used solely during initial prototyping and have since been revoked.

### Credential Management Policy

- **All demo credentials must be generated at container startup via entrypoint scripts.** Credentials are never committed to the repository.
- Secrets are injected at runtime through environment variables or Docker secrets.
- The `.gitignore` file is configured to exclude common credential file patterns.
- CI pipelines include secret-scanning steps to prevent accidental commits.

### Additional Security Measures

- Dependencies are monitored via Dependabot for known vulnerabilities.
- Docker images are built from minimal base images to reduce attack surface.
- All inter-service communication within the control plane uses authenticated channels.

## Scope

This security policy applies to the Vulcan control plane repository and its official Docker images. Third-party integrations and forks are outside the scope of this policy.
