# Security Policy

## Supported Versions

Only the [latest release](https://github.com/StefanBS/battle-city-clone/releases/latest) gets security fixes. Fixes are not backported to older releases, so update to the latest one before reporting.

## Reporting a Vulnerability

Please do not open a public issue for a security problem. Report it privately through GitHub instead:

**[Report a vulnerability](https://github.com/StefanBS/battle-city-clone/security/advisories/new)**

Include what you found, how to reproduce it, and which release or commit you tested.

This is a hobby project maintained in spare time, so responses are best effort. You can expect an acknowledgement within a week or two. If the report is confirmed, the fix ships in a new release and the advisory is published once that release is out.

## Scope

In scope:

- The release artifacts: the Flatpak bundle and the Windows installer
- The CI and release workflows in `.github/workflows/`
- The game's dependencies, as pinned in `uv.lock`
- The game itself, for example loading a crafted map or `settings.json` file

Gameplay bugs, crashes that need no crafted input and balance problems are not security issues. Please report those as regular [issues](https://github.com/StefanBS/battle-city-clone/issues).
