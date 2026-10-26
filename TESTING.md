# Independent audit — 2026-10-26

[AUDIT.md](AUDIT.md) records **122 PASS / 0 FAIL / 12 UNTESTED** across 134 rows, with zero PENDING and zero testable FAIL. The final run executed **G1–G134 in table order**, including every previous PASS: 86 browser/API checks and 36 local CLI, protocol, algorithm and documentation checks. [Timestamped order](audit/sequence.jsonl) and [run metadata](audit/run.json) identify this run.

`.venv/bin/python -m pytest -q` exited **0: 57 passed in 68.00s (0:01:07)**. Test collection independently reported 57 tests. [Full output](audit/pytest-final.txt).

Chrome for Testing **156.0.8078.4**, driven by Playwright, tested the production `web/dist` served by `.venv/bin/python -m hub.server --host 127.0.0.1 --port 8780` at **http://127.0.0.1:8780**. Desktop width was 1440px; phone width was 375px. The served index matched the built file byte for byte. `npm run build --prefix web` passed and reproduced the existing build.

G8 passed with the model configuration unset: the Reason lamp displayed **Setup required: NEBIUS_API_KEY**, `model.online` was false, and capture attribution stayed on rules/templates. The browser and hub socket-connect logs recorded **zero requests to api.tokenfactory.nebius.com**, Twilio or Telegram. The missing-credential alert functions returned `printed`, with no socket connection. Live Nebius rows G116/G117 and the ten unavailable hardware/alert rows remain **UNTESTED**, each with its exact dependency in [dependencies.json](audit/dependencies.json).

Every browser row retains console, page-error and network evidence. There were **zero page errors, unexpected console/network errors or HTTP 500 responses**. Expected negative probes (400/404/405/409), deliberate hub shutdowns and intentional stream cancellation remain visible in the logs; they are not counted as normal successful requests.

No mocks, response stubs or substituted snapshots stood in for the tested browser surface or production rules, sensing, persistence and routing logic. The following simulations remain explicit:

- The bundled replay and 14-day routine are synthetic and labelled in the product; HOTARU is explicitly virtual.
- G101 runs the actual, explicitly synthetic `hub.fake_lamp` CLI against real localhost TCP/UDP, including retry, hello, CSI, commands and voice reply. Protocol unit tests also use `FakeLamp`; none validates physical hardware.
- Four full-suite model tests replace `Reasoner._chat`: two in `tests/test_agent.py` and two in `tests/test_evidence.py`. They verify local contracts only and do not establish live Nebius success.
- G3/G49/G51 delay genuine HTTP requests to reproduce boot, interruption and refusal races; they do not replace any response. EventSource instrumentation only records real snapshots and connection counts. Local algorithms use deterministic input fixtures and real JSON files.

No production fix was needed in this re-audit. The audit harness now executes rows in order, resets each required precondition, allows the full wall-clock check-in cycle, observes CLI socket connections separately and exercises the fake-lamp CLI directly. G32/G77/G82 passed from their starting states after correcting harness timing, setup and SSE synchronization, followed by the entire final run. Existing product fix commits remain named per former FAIL in AUDIT.md.

Only the final full-plan evidence is retained. All 86 screenshots are WebP, the largest is **93,930 bytes** (limit 200,000), and `audit/` remains below 15 MiB. [Final checks](audit/final-verification.json) and [cleanup](audit/resource-cleanup.json) record the assertions, owned PIDs, no remaining owned hub/Chrome/CLI processes and release of **ghost-nebius-reaudit** through an EXIT trap. Unrelated processes were left alone. No external service call, deployment, mainnet action, real-money action or origin push was made.

Final-run commands (the browser harness invokes each selected local row itself):

```sh
npm run build --prefix web
unset NEBIUS_API_KEY GHOST_REASON_MODEL GHOST_LOG_MODEL GHOST_LLM_BASE_URL
unset TWILIO_ACCOUNT_SID TWILIO_AUTH_TOKEN TWILIO_FROM ALERT_PHONE TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
slot='/Volumes/Extreme SSD/Projects/grokbot/tools/heavy-slot.sh'
"$slot" acquire ghost-nebius-reaudit
trap '"$slot" release ghost-nebius-reaudit' EXIT
node audit/browser-audit.mjs
.venv/bin/python -m pytest -q > audit/pytest-final.txt 2>&1
.venv/bin/python audit/finalize-audit.py
```

This run used the existing project Python environment and web dependencies through temporary worktree links; Playwright is installed under `/tmp/ghost-browser-tools`. The Chrome executable is recorded in the harness. These worker changes are left uncommitted for Loom, as required by the authoritative session instructions. [Existing fix commit subjects](audit/commit-subjects.txt) remain available for review.
