# Release draft — Jarvis Ultimate Tool v1.0-intercept

**Date:** 2026-02-19
**Target branch:** main
**Prerelease:** false (final)

## Summary
This release adds a major set of features focused on reliable captive‑portal activation workflows and real‑time interception tooling for diagnostics. It includes a local DNS interceptor, MITM‑friendly captive portal with signed `.mobileconfig` support (OpenSSL + cryptography fallback), and WebSocket-backed real‑time feedback that connects the portal to the desktop UI.

## Highlights
- Traffic interception: `scripts/dns_server.py` provides a local DNS resolver that intercepts Apple activation hostnames (albert.apple.com, gs.apple.com, captive.apple.com) and resolves them to the local machine — enabling reliable captive‑portal routing for iOS testing and ticket capture.
- Captive portal redesign: `web/captive_portal.html` reworked with an iOS‑style UI and guided flow to install `server.crt` and `.mobileconfig` profiles. Bigger CTAs, QR support and improved status indicators for a smoother mobile experience.
- Profile signing resilience: server attempts to sign `.mobileconfig` with the OpenSSL CLI; if not available, a `cryptography` PKCS7 fallback is used (no CLI dependency). See `profile_generator.py`.
- Real‑time feedback: WebSocket endpoint `/ws` and server-side events queue let the portal notify the desktop app instantly; desktop now shows a live "Intercepción" console and status cards (`main.py`).
- MITM‑friendly capture: `portal_server.py` now captures POST/PUT payloads from targeted Apple hosts and stores them under `logs/` (for ticket extraction and diagnostics).
- Headless & CI verification: `scripts/press_buttons_headless.py` + `scripts/verify_setup.py` provide automated smoke tests for the portal and UI flows; included in CI to prevent regressions.
- Packaging & release: PyInstaller spec and CI job updated to produce Windows installer and executable artifacts.

## Files changed (notable)
- Added: `scripts/dns_server.py`, `scripts/verify_setup.py`, `scripts/get_device_info.py`, `scripts/show_ticket.py`
- Modified: `portal_server.py`, `web/captive_portal.html`, `main.py`, `profile_generator.py`, `README.md`, `requirements.txt`, tests and CI configs

## Security & privacy notes
- Captured activation tickets and payloads are sensitive — stored under `logs/`. Do **not** publish logs or tickets.
- `certs/` contains example/test certificates for local debugging. Replace or remove before publishing to a public repo/release.
- DNS interception requires device configuration (or elevated privileges to bind to port 53).

## How to use (quick start)
1. Install dependencies: `pip install -r requirements.txt`.
2. Start the portal: `python portal_server.py` (or use the bundled exe).
3. (Optional) Start DNS interceptor (admin required): `python -m scripts.dns_server` — or configure iPhone DNS to point to the machine IP.
4. Open the portal on the test device and follow the UI to download `server.crt` and install the `.mobileconfig` profile.
5. Watch the desktop "Intercepción" panel — captured tickets appear in `logs/activation_ticket_*.xml`.

## Known limitations
- Full end‑to‑end activation capture requires trusted `server.crt` on the iOS device and DNS redirection of Apple activation hostnames.
- Port 53 binding requires admin privileges; for local tests use a high port (5353) and configure device to use that DNS.
- This tool is for legitimate diagnostics and recovery only. Do not use it to bypass Activation Lock or any security mechanisms.

## Tests & validation
- Unit tests: all existing tests pass locally (`pytest -q`).
- Headless smoke: `scripts/press_buttons_headless.py` verifies main UI flow.
- CI: `scripts/verify_setup.py` added to PR checks for portal endpoints and signing behavior.

## Release artifacts
- Windows executable and installer (created via PyInstaller + Inno Setup) — attached to this release.
- `README.md` updated with DNS / certificate instructions and verification steps.

## Changelog (brief)
- Added: DNS interceptor + request capture, WebSocket events, portal UI redesign, profile signing fallback, headless verifier, tests and packaging.

---

### Maintainer notes (for the release page)
- Tag: `v1.0-intercept` (recommended)
- Release title: "Jarvis Ultimate Tool — Captive‑Portal & Interception (v1.0‑intercept)"
- Release description: use the content above (Summary + Highlights + Quick Start)
- Attach: `dist/ACTIVATOR-TOOL/ACTIVATOR-TOOL.exe`, installer `.exe`, and `CHANGELOG.md` if available

---

If you want, I can (choose one):
- A) create the Git tag `v1.0-intercept` and push it to `origin` now
- B) open a GitHub Release draft with this content (I will create `RELEASE_DRAFT.md` only)

Please tell me whether to proceed with the tag push or just keep this draft.  
