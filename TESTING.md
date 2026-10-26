# Verified audit — 2026-10-26

AUDIT.md contains **122 PASS, 0 FAIL, 12 UNTESTED** across 134 rows. No testable row remains PENDING. The final run contains 86 browser/API rows and 36 local CLI/algorithm/documentation rows.

The complete command `.venv/bin/python -m pytest -q` exited **0: 57 passed in 68.02s**. The Phase 1 baseline was 47 passed; ten regressions were added. See [the full-suite output](audit/pytest-final.txt).

Chrome for Testing **156.0.8078.4**, driven through Playwright, tested the committed `web/dist` served by `python -m hub.server` at **http://127.0.0.1:8780**. The index served by the hub matched the built file byte for byte. Desktop checks used 1440px width; phone checks used 375px. Screenshots, console/page errors, and requests/responses are linked per row in [AUDIT.md](AUDIT.md).

G8 passed with NEBIUS_API_KEY, GHOST_REASON_MODEL and GHOST_LOG_MODEL unset: the Reason lamp displayed **Setup required: NEBIUS_API_KEY**, `model.online` was false, and captures used rules/templates. No Token Factory request was sent. The browser request log and the hub's observed outbound socket-connect log also show no Twilio or Telegram request during replay. Missing-credential alert functions returned `printed`.

Normal browser flows had no console errors, page errors, failed requests, or unexpected HTTP errors. Deliberate hub shutdowns, explicit negative API probes and intentional stream cancellation are identified in their logs. G83's four 404 responses are required by its expected result; its classification was corrected against the unchanged raw console/network evidence. No HTTP 500 or page error was accepted.

No replacement snapshots, mocked cloud responses, or fallback sensor data were used for browser passes. The bundled night retained its **synthetic night** label and synthetic-history disclaimer. Virtual HOTARU stayed explicitly virtual. Existing model-mocked unit tests are not evidence of live Nebius integration. The twelve [missing-dependency rows](audit/dependencies.json) remain UNTESTED; physical ESP32/HOTARU operation and live alert sends are not claimed.

Local rows retain actual command output and per-row assertions. Their shared dashboard screenshot provides running-product context, not proof of the CLI result. Headless save/reload was exercised through the real CLI; the production maintenance function also wrote/read a real JSON journal across an eligible calendar boundary and verified that a second tick did not fit another model. That test used the bundled synthetic history and explicit timestamp inputs, without substituting routine logic, cloud services, hardware or a clock implementation.

Every screenshot is WebP and at most 200,000 bytes. Only final-plan evidence is retained; `audit/` is under 15 MiB. [Cleanup evidence](audit/resource-cleanup.json) records the owned hub/Chrome PIDs and slot release. Port 4180 and unrelated processes were left alone. Nothing was pushed or deployed.

To reproduce on this machine, install the Python requirements, run `npm ci` in `web/`, and install Playwright with `npm install --prefix /tmp/ghost-browser-tools playwright`. The browser harness uses the installed Chrome for Testing binary. Acquire the shared heavy slot in the foreground before the browser harness, and release it in an EXIT trap:

```sh
/Volumes/Extreme\ SSD/Projects/grokbot/tools/heavy-slot.sh acquire ghost-nebius-audit
trap '/Volumes/Extreme\ SSD/Projects/grokbot/tools/heavy-slot.sh release ghost-nebius-audit' EXIT
node audit/browser-audit.mjs
```

Run `audit/local-audit.py` while the same audit owns the slot, because its headless CLI checks bind local hub sockets. Run the full pytest command above, then `audit/finalize-audit.py`; finalization rejects missing rows, failures, changed expected results, oversized screenshots or excess evidence size.

[Commit subjects](audit/commit-subjects.txt) list the separate fixes and final evidence commit.
