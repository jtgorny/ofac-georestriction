# Security Policy

## Supported versions

Security fixes are applied to the default branch and included in the next tagged release. Older
releases are not maintained as separate support lines.

## Report a vulnerability

Do not open a public issue for a suspected vulnerability, exposed credential, or sensitive source
data. Use the repository's
[private vulnerability reporting form](https://github.com/jtgorny/ofac-georestriction/security/advisories/new).

Include:

- the affected file, workflow, endpoint, or release;
- reproduction steps that do not expose a real credential;
- the impact and likely attack path;
- any mitigation you have already tested.

Do not include API keys, access tokens, private customer data, or exploit traffic against upstream
sanctions sources. A maintainer will acknowledge the report through GitHub's private advisory
thread and coordinate validation, remediation, and disclosure there.

## OpenAI API key handling

`OPENAI_API_KEY` is optional and must be treated as a secret:

- store it in a GitHub Actions repository secret or an approved secret manager;
- expose it only to the server-side build process;
- never write it to `docs/`, logs, source files, shell commands, screenshots, or scratchpads;
- use a project-specific key with the minimum permissions and an appropriate spend limit;
- rotate it periodically and immediately after suspected exposure.

If a key may have been exposed:

1. Delete or rotate it in the OpenAI API key dashboard.
2. Update the GitHub Actions secret or local secret-manager entry.
3. Review API usage and project spend for unexpected activity.
4. Search the working tree, Git history, workflow logs, artifacts, and shared backups.
5. Report any repository exposure through the private vulnerability form above.

Removing a secret in a later commit does not remove it from Git history. History rewriting and
cache invalidation may be required if a credential was ever committed.

For current provider guidance, see
[OpenAI's API key safety practices](https://help.openai.com/en/articles/5112595-best-practices-for-api-key).

## Public-data boundary

Everything under `docs/` is deployed publicly. The generator must not publish credentials,
customer-specific policy notes, internal hostnames, private sanctions interpretations, or raw
provider error responses. Manual override notes should be written for public consumption.

## Scope and limitations

Security reports about this project's code, workflows, generated artifacts, and deployment are in
scope. Questions about the legal correctness of a sanctions decision are not security
vulnerabilities and require qualified counsel. Do not test the availability or security of OFAC,
EU, UK, UN, OpenAI, or GitHub systems on this project's behalf.
