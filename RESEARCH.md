# GHOST research notes: hackathon, Nebius, NVIDIA, prior art

All links accessed **2026-10-17**. Items marked **[unverified]** are inferences or claims I could not confirm against a primary source. I did not sign up for anything or call any paid or authenticated API.

---

## What this means for GHOST

```bash
export GHOST_LLM_BASE_URL=https://api.tokenfactory.nebius.com/v1        # matches hub/agent.py default
export NEBIUS_API_KEY=...                                               # sent as "Authorization: Bearer $NEBIUS_API_KEY"
export GHOST_REASON_MODEL=nvidia/Nemotron-3-Ultra-550b-a55b             # "Ultra": deep reasoning about events
export GHOST_LOG_MODEL=nvidia/Nemotron-3_5-Lightning                    # fast 30B-A3B; or nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B
```

- **The deadline is earlier than the repo says.** Devpost lists **Fri Oct 30, 2026, 10:00 AM PT**. `REQUIREMENTS.md` says 10:30 PM PT, which would be 12.5 hours too late. Plan to submit on Oct 29. ([Rules §1](https://nebiusglobalaihackathon.devpost.com/rules))
- **Model IDs are case-sensitive and inconsistent.** Copy them exactly as written, including `Nemotron-3_5-Lightning` (underscore), `Nemotron-3-Ultra-550b-a55b` (lowercase "b") and `nemotron-3-super-120b-a12b` (all lowercase). ([public catalog JSON](https://tokenfactory.nebius.com/api/public/models_info))
- **Two models from the brief are no longer usable.** `Llama-3_1-Nemotron-Ultra-253B-v1` left Token Factory Serverless on Aug 31, 2026. Nemotron Nano 9B v2 is not in the current public catalog. ([Aug 2026 deprecation notice](https://docs.tokenfactory.nebius.com/august-2026-deprecation-notice))
- **Why Lightning for log lines.** It costs the same as Nemotron 3 Nano ($0.06 in / $0.24 out per 1M tokens), but the catalog lists it at about 314 tok/s against about 60 tok/s for Nano, with a 1M context window. If you want the word "Nano" on screen for the judges, `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` works as a drop-in replacement. ([catalog](https://tokenfactory.nebius.com/model-catalog.md))
- **Turn reasoning off for log lines** with `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`. Token Factory's OpenAPI spec also exposes `reasoning_effort` (`none`…`max`). **[unverified]** I have not confirmed which of the two Token Factory actually honours for Nemotron, so test both. (See §2.)
- **Physical AI rules that matter for GHOST.** The video must include at least 1 minute of real hardware (ESP32 mesh + Hotaru lamp) operating. You do not need a hosted demo URL. Judges may ask for physical access to the hardware. The repo needs an OSI licence shown in the GitHub About box (the repo has MIT, which qualifies), plus the required feedback section. ([Rules §6–7](https://nebiusglobalaihackathon.devpost.com/rules))
- **Free credits.** $25 of Token Factory credit through the promo form (code `NEBIUS-DEVPOST-GLOBAL26`), plus another $25 from the Nebius Builders Program. There is **no published AI Cloud credit grant**, so Serverless Jobs and Endpoints are billed at Compute rates. ([Resources](https://nebiusglobalaihackathon.devpost.com/resources), [FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs))
- **Speech is not on Token Factory.** Magpie TTS and Parakeet ASR are on build.nvidia.com (NVIDIA NIM), not on Nebius. A Deepgram-to-NVIDIA swap would therefore call NVIDIA's hosted API, or a self-hosted NIM container on a Nebius Serverless Endpoint **[unverified that this works]**. (See §4.)
- **Prior art risk: RuView already advertises routine and anomaly learning.** RuView lists modules for "daily routines" and "learns what's normal", an on-device LLM, and fall alerts. Pitch GHOST's novelty as the *combination*: alerts explained by Nemotron that cite the sensor evidence, plus an embodied responder (Hotaru). Do not claim that routine learning by itself is new. (See §5.)

---

## 1. The hackathon

**Official page:** Devpost, "Nebius x NVIDIA Global AI Hackathon: Build the next frontier of AI on open infrastructure". [Overview](https://nebiusglobalaihackathon.devpost.com/), [Rules](https://nebiusglobalaihackathon.devpost.com/rules), [Resources](https://nebiusglobalaihackathon.devpost.com/resources), [FAQs](https://nebiusglobalaihackathon.devpost.com/details/faqs), [Updates](https://nebiusglobalaihackathon.devpost.com/updates). Sponsor: Nebius B.V. Administrator: Devpost. About 24,300 participants at the time of access.

### Dates ([Rules §1](https://nebiusglobalaihackathon.devpost.com/rules))
| Phase | When (Pacific Time) |
|---|---|
| Submission period | Wed Aug 26, 2026 9:00 AM to **Fri Oct 30, 2026 10:00 AM** |
| Judging | Tue Dec 1, 2026 9:00 AM to Tue Dec 15, 2026 12:00 PM |
| Winners announced | on or around Mon Jan 11, 2027 12:00 PM |

The "Will It Ship" judges' session on the judging criteria is **Tue Oct 20, 9 AM PT**. ([Updates](https://nebiusglobalaihackathon.devpost.com/updates))

### Required tech ([Overview](https://nebiusglobalaihackathon.devpost.com/), [Rules §5](https://nebiusglobalaihackathon.devpost.com/rules))
- Every project must "run on either Nebius Token Factory or Nebius AI Cloud and use at least one NVIDIA open source model".
- "Runs on" means "a runtime call to the Token Factory inference API, or is deployed/run using Nebius AI Cloud compute (Serverless Jobs, Serverless Endpoints, or DevPods)."
- Calling an NVIDIA model through another provider, such as HuggingFace or OpenRouter, does **not** count. The rest of the app does not have to be hosted on Nebius. ([FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs))

### Tracks ([Overview](https://nebiusglobalaihackathon.devpost.com/))
Coding and Agentic Engineering · Best Apps and Agents · Personal AI · **Physical AI**.

**Physical AI track brief (verbatim):**
> Build embodied and edge agents that sense and act in the real world: robotics, IoT, and on-device intelligence, powered by Nemotron, GROOT, Cosmos and Sonic models and coordinated through an agent runtime. Use Nebius Serverless Jobs to run simulations, generate synthetic data, evaluate robot policies, or process sensor data at scale, and Nebius Serverless Endpoints to serve real-time inference when needed. Your demonstration video must include at least a 1-minute clip showing the physical hardware/robot actually operating, or — if your project has no physical hardware component — the key application modules in action.

- Simulation such as Isaac Sim is allowed, and there is no required hardware list. Other NVIDIA open models, such as Alpamayo, are also allowed. ([FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs))
- The Best Apps and Agents brief gives this model-tiering advice: "Reach for Nemotron 3 Ultra when you need serious reasoning, and let Nano or Super handle the fast, everyday calls". GHOST's two-model split follows it. ([Overview](https://nebiusglobalaihackathon.devpost.com/))

### Judging ([Rules §6](https://nebiusglobalaihackathon.devpost.com/rules))
- **Stage One (pass/fail):** does the project fit the theme and use the required APIs? The rules add that a fitting project is "a genuine attempt at the track's stated goal, not a superficial rebrand of an unrelated idea."
- **Stage Two:** the criteria below are **"equally weighted"**. No percentages are published, so 25% each is implied. Ties are broken by criterion order, Technological Implementation first.
  1. **Technological Implementation**: "How well is the project built, and how effectively does it use Nebius Token Factory or AI Cloud model(s), and NVIDIA Nemotron or other NVIDIA open source models as part of the solution?"
  2. **Design**: "Does the project deliver a complete, coherent product experience not just a technical proof of concept?"
  3. **Potential Impact**: "Does the project make a credible, specific case for solving a real problem for a real audience and does the solution actually address it based on what's demonstrated?"
  4. **Quality of the Idea**: "Is this a creative, non-obvious use of Nebius Token Factory or AI Cloud model(s), and NVIDIA Nemotron or other NVIDIA open source models and does the team show genuine understanding of the problem space?"
- **Feedback prize:** judged on "completeness, viability, and potential impact of the feedback."

### Submission requirements ([Rules §5](https://nebiusglobalaihackathon.devpost.com/rules), [Overview](https://nebiusglobalaihackathon.devpost.com/))
- **Working demo URL:** "not required for Physical AI submissions". Judges *may* require physical access to hardware that is not widely available.
- **Text description:** what it is, why it was built, and how it works. You must also pick a track.
- **Video:** **under 3 minutes**, on public YouTube, with no copyrighted music. Physical AI entries need **at least 1 minute of the hardware actually operating**. Show the Token Factory and Nemotron usage.
- **Public repo** on GitHub, GitLab or Bitbucket, with an OSI licence (Apache 2.0, MIT or MPL 2.0) "visible at the top of the repository page (in the About section)". It also needs a README with setup steps, and the README must highlight the Nemotron usage, "where Token Factory accelerated your workflow", and any other Nebius services used.
- **Feedback** on Token Factory, AI Cloud and the NVIDIA models used. This is **required**. The organisers ask for what you used, what worked, what needs work, onboarding from zero to hello world, and whether you would build with them again. ([Updates](https://nebiusglobalaihackathon.devpost.com/updates))
- If the project existed before Aug 26, include a written note on what was significantly updated during the submission period.

### Prizes ([Rules §8](https://nebiusglobalaihackathon.devpost.com/rules))
| Prize | Award |
|---|---|
| Grand / 2nd / 3rd | $20,000 / $10,000 / $6,000 |
| Track winners (×4, incl. **Physical AI**) | 1 NVIDIA Jetson Orin Nano each |
| Best Use of Tavily | $3,000 (needs a runtime Tavily API call) |
| City Winner (×20) | $500 (requires attending a Builders & Brews event in person) |
| **Most Valuable Feedback** (×10) | $100 + NVIDIA swag pack |

A project can win **one** Overall award, **or** one Track award plus one Bonus award.

---

## 2. Nebius Token Factory (formerly AI Studio)

- **Base URL:** `https://api.tokenfactory.nebius.com/v1/` (OpenAI-compatible). ([Quickstart](https://docs.tokenfactory.nebius.com/quickstart))
  - Regional variants exist, for example `api.tokenfactory.eu-west1.nebius.com/v1/`. Nebius warns that public serverless models are "Global" and regional URLs "can stop working", so use the global URL. ([Public Serverless Endpoints](https://docs.tokenfactory.nebius.com/public-serverless))
  - The old `api.studio.nebius.com` host still answers with 401 when called without a key. **[unverified]** I have not confirmed whether it works as an alias.
- **Auth:** send `Authorization: Bearer $NEBIUS_API_KEY`. The key is created under API keys at tokenfactory.nebius.com and is shown only once. ([Quickstart](https://docs.tokenfactory.nebius.com/quickstart))
- **Model list:** `GET /v1/models` (auth required). A public, unauthenticated catalog is at [`/api/public/models_info`](https://tokenfactory.nebius.com/api/public/models_info) (JSON, which Nebius calls "authoritative") and [`/model-catalog.md`](https://tokenfactory.nebius.com/model-catalog.md).

### NVIDIA Nemotron models currently in the public catalog ([models_info JSON](https://tokenfactory.nebius.com/api/public/models_info))
| Model ID (exact) | Role for GHOST | Context | Price $/1M (in / out) | Listed tok/s | Licence |
|---|---|---|---|---|---|
| `nvidia/Nemotron-3-Ultra-550b-a55b` | **REASON** (550B MoE, 55B active) | 1,048,576 | 1.00 / 3.00 | 523 | OpenMDW-1.1 |
| `nvidia/nemotron-3-super-120b-a12b` | cheaper reasoning fallback | 262,144 | 0.30 / 0.90 | 127 | NVIDIA Open Model Licence |
| `nvidia/Nemotron-3_5-Lightning` | **LOG** (30B, 3B active, MTP) | 1,048,576 | 0.06 / 0.24 | 314 | OpenMDW v1.1 |
| `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | LOG alternative ("Nano") | 262,144 | 0.06 / 0.24 | 60 | NVIDIA Open Model Licence |
| `nvidia/Nemotron-3.5-Super-VL` | vision-language (not needed) | 1,024,000 | 0.30 / 0.90 | 282 | OpenMDW-1.1 |

- All five are tagged `reasoning`, `function_calling` and `responses_api` in the catalog. The tok/s figures are Nebius's catalog numbers, not my own benchmarks.
- **Not available:** `nvidia/Llama-3_1-Nemotron-Ultra-253B-v1` was removed from Serverless on Aug 31, 2026; Nebius's suggested replacement is Super. `nvidia/Nemotron-3-Nano-Omni` was also removed, replaced by Lightning. ([deprecation notice](https://docs.tokenfactory.nebius.com/august-2026-deprecation-notice)) Nemotron Nano 9B v2 is not listed.

### Reasoning toggle
- The NVIDIA model cards for Nano, Super, Ultra and Lightning all say the same thing. Reasoning is **on by default** and is toggled through the chat template: `extra_body={"chat_template_kwargs": {"enable_thinking": False}}`.
  - Super also supports `{"enable_thinking": True, "low_effort": True}`.
  - The Nano card also documents a `/think` system-prompt suffix and a client-side `reasoning_budget`.
  - Sources: [Nano card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16), [Super card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-FP8), [Ultra card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16), [Lightning card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16).
- **Ultra card gotcha:** when sending `tools`, you "must set `"chat_template_kwargs": {"enable_thinking": true, "force_nonempty_content": true}`". ([Ultra card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16))
- **On Token Factory specifically:** the `ChatCompletionRequest` schema has `reasoning_effort` (`none|minimal|low|medium|high|xhigh|max`) and a generic `extra_body`. ([OpenAPI spec](https://api.tokenfactory.nebius.com/openapi.json)) **[unverified]** I could not confirm, without an API key, whether `chat_template_kwargs` is passed through or whether `reasoning_effort` maps to `enable_thinking` for Nemotron. Test both with a single request each.
- Reasoning text usually comes back in `message.reasoning_content`, separate from `content`. That is the vLLM convention shown in the Nano card. **[unverified on Token Factory]**

### Structured output and tool calling
- **JSON:** `response_format={"type":"json_schema","json_schema":{"name":…,"schema":…,"strict":true}}` or `{"type":"json_object"}`. The docs advise putting the schema in the prompt as well. Support varies by model; look for the "JSON mode" tag on the model card. ([Structured output](https://docs.tokenfactory.nebius.com/ai-models-inference/json), [OpenAPI](https://api.tokenfactory.nebius.com/openapi.json))
- **Tools:** OpenAI-format `tools` and `tool_choice` (`auto`, `none`, `required`, or a named function). ([Function calling](https://docs.tokenfactory.nebius.com/ai-models-inference/function-calling))
- **Rate limits** scale with usage tier. ([Rate limits](https://docs.tokenfactory.nebius.com/ai-models-inference/rate-limits))

---

## 3. Nebius Serverless AI (AI Cloud): Jobs and Endpoints

- **What it is:** containerised workloads on managed Compute container VMs, with three types. ([About Serverless AI](https://docs.nebius.com/serverless/overview))
  - **Devlab:** interactive IDE.
  - **Job:** runs to completion; no public URL; disk wiped when finished.
  - **Endpoint:** serves requests at a public URL; can be stopped and started.
- **Fit for GHOST:**
  - The Physical AI brief names Jobs for "process sensor data at scale" and Endpoints for "real-time inference". ([Overview](https://nebiusglobalaihackathon.devpost.com/))
  - A nightly routine-retraining **Job** would satisfy "runs on AI Cloud" on its own, in addition to the Token Factory calls.
  - Hosting the hub or agent as an **Endpoint** is possible but optional.
- **Creating a Job (CLI):**
  - Command: `nebius ai job create --name … --image … --container-command … --args … --platform … --preset … --timeout …`. Other flags include `--env`, `--env-secret`, `--volume` and `--restart-policy`.
  - `nebius ai create --type job` gives the same thing interactively. The web console has quick-start cards.
  - REST: `POST https://api.nebius.cloud/ai/v1/jobs`.
  - Sources: [Jobs quickstart](https://docs.nebius.com/serverless/quickstart/jobs), [Managing jobs](https://docs.nebius.com/serverless/jobs/manage), [CLI ref](https://docs.nebius.com/cli/reference/ai/job/create).
- **Creating an Endpoint (CLI):**
  - Command: `nebius ai endpoint create … --platform cpu-d3 --preset 4vcpu-16gb --auth token --token "$AUTH_TOKEN"`.
  - Requests then carry `Authorization: Bearer <endpoint_token>`.
  - Source: [Endpoints quickstart](https://docs.nebius.com/serverless/quickstart/endpoints). There is also an [LLM-serving tutorial](https://docs.nebius.com/serverless/tutorials/deploy-model).
- **Scheduling:** the docs describe jobs as "one-off or scheduled batch workloads". However, I found **no schedule or cron flag** in the CLI reference. **[unverified]** For "nightly", plan on an external trigger, such as host cron or a GitHub Actions cron, running `nebius ai job create`. ([Managing jobs](https://docs.nebius.com/serverless/jobs/manage))
- **Pricing:**
  - Serverless has no separate price list. It uses Compute VM and disk pricing, billed per second while running. Stopped endpoints cost nothing; jobs cannot be stopped. ([Pricing & quotas](https://docs.nebius.com/serverless/pricing-quotas), [Compute pricing](https://docs.nebius.com/compute/resources/pricing))
  - Availability is listed as all regions except eu-north2, us-north1 and uk-south2. ([Serverless index](https://docs.nebius.com/serverless/index))
- **Hackathon credits:** Token Factory only, $25 from the form plus $25 from the Builders Program. The FAQ says "there isn't a separate published AI Cloud credit grant". Builders & Brews attendees "can also unlock additional Nebius AI Cloud" credits. ([FAQ](https://nebiusglobalaihackathon.devpost.com/details/faqs), [Resources](https://nebiusglobalaihackathon.devpost.com/resources))

---

## 4. NVIDIA open speech models (Deepgram replacement)

| Model | What | Where to call it | Licence |
|---|---|---|---|
| **Magpie TTS Multilingual** (357M) | TTS, 12 languages, "ready for commercial use" | Hosted NIM at [build.nvidia.com/nvidia/magpie-tts-multilingual](https://build.nvidia.com/nvidia/magpie-tts-multilingual) through the Riva gRPC client (`grpc.nvcf.nvidia.com:443`, `function-id 877104f7-e885-42b9-8de8-f6e4c6303969`, `nvapi-` key). Weights on [HF](https://huggingface.co/nvidia/magpie_tts_multilingual_357m). | Weights: [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license) ([HF card](https://huggingface.co/nvidia/magpie_tts_multilingual_357m)). The hosted API falls under NVIDIA API Trial terms (per search results). |
| **Parakeet TDT 0.6B v2** (EN) / **v3** (25 European languages) | ASR | v2 is a hosted NIM at [build.nvidia.com/nvidia/parakeet-tdt-0_6b-v2](https://build.nvidia.com/nvidia/parakeet-tdt-0_6b-v2) (Riva gRPC, `function-id d3fe9151-442b-4204-a70d-5fcc597fd610`). A NIM container is on [NGC](https://catalog.ngc.nvidia.com/orgs/nim/nvidia/containers/parakeet-0.6b-tdt/). | **CC-BY-4.0** ([v2 card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2), [v3 card](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3)) |
| Riva TTS / ASR NIM (self-hosted) | containers for the models above | [Riva TTS NIM docs](https://docs.nvidia.com/nim/riva/tts/1.6.0/getting-started.html). Production use needs NVIDIA AI Enterprise (90-day eval offered). | NVIDIA Software License + AI Enterprise |

- **Not on Nebius Token Factory.** The public catalog lists only text, image-to-text and embedding models; there are no audio models. ([models_info](https://tokenfactory.nebius.com/api/public/models_info))
  - Nebius's own Serverless TTS tutorial uses Piper and Whisper, not Magpie or Parakeet. ([TTS tutorial](https://docs.nebius.com/serverless/tutorials/tts))
  - **[unverified]** Running the Parakeet or Magpie NIM container on a Nebius Serverless Endpoint (GPU) should work in principle, since any container is allowed, but I found no Nebius guide for it.
- **Hackathon angle:** the speech models count as "other NVIDIA open source models". However, calling them on build.nvidia.com does **not** satisfy the Nebius-runtime rule. That rule is already met by the Nemotron calls on Token Factory.
- **Hosted API keys:** the model cards say build.nvidia.com hosted calls use a free trial API key. Rate limits and terms are not documented on the cards. **[unverified]**

---

## 5. Prior art to acknowledge

- **RuView** ([ruvnet/RuView](https://github.com/ruvnet/RuView), MIT, about 98k stars, pushed 2026-10-17): ESP32-S3/C6 CSI for presence, breathing, heart rate, falls and pose, with no cameras.
  - Its README lists modules for "Detects daily routines and repeated habits" (`pattern-sequence`) and "Learns what's normal and catches anything weird" (`anomaly-attractor`), an on-device SmolLM2 "cognitive-pipeline", fall alerts, Home Assistant and Matter integration, and an MCP server for ChatGPT and Claude.
  - **This overlaps GHOST heavily.** Its accuracy claims are self-reported, and some coverage has questioned the project. ([README](https://raw.githubusercontent.com/ruvnet/RuView/main/README.md), [CNX Software](https://www.cnx-software.com/?p=167773))
- **"WiFi Sense"** is wifisense-pi by [The Masked Bear], covered by Hackaday on Aug 15, 2026 as "Scanning For Lifesigns With ESP32 And Raspberry Pi".
  - Setup: an ESP32-S3 samples the channel at 100 Hz, and a Raspberry Pi 4 does the DSP. It detects a still person through the micro-motion of breathing, and works through walls.
  - Limits: a single sensor gives no position and cannot separate multiple people.
  - [Hackaday](https://hackaday.com/2026/08/15/scanning-for-lifesigns-with-esp32-and-raspberry-pi-now-open-source/), [repo](https://github.com/The-Masked-Bear/wifisense-pi). **[unverified]** That this is the article you meant: no Hackaday piece titled exactly "WiFi Sense" was found.
- **CardioNet** (Devpost): two ESP32s as transmitter and receiver, with an LSTM estimating heart rate from CSI. It is framed for elderly care and was built in 36 hours. ([Devpost](https://devpost.com/software/tbd-8dozbj))
- **Origin Wireless**: a commercial Wi-Fi sensing company (wirelessAI, "Time Reversal Machine") offering breathing and fall detection for elder care. When a fall is detected it switches to breathing analysis, then alerts a caregiver. Won 2021 CES awards. ([Origin post](https://www.originwirelessai.com/post/powered-by-origin-wifi-sensing-tech-will-soon-be-everywhere), [Engadget 2017](https://www.engadget.com/2017-10-09-origin-wireless-motion-detection-breathing-rate-sensor.html), [UMD news](https://ece.umd.edu/news/story/origin-wireless-wins-two-2021-ces-awards-including-best-innovation-award))
- **IEEE 802.11bf-2025** (WLAN Sensing amendment): approved by the IEEE SA Standards Board on 28 May 2025 and published on 26 Sep 2025. It covers sensing in 1–7.125 GHz and above 45 GHz. ([standard PDF mirror](https://people.freebsd.org/~adrian/net80211/80211bf-2025.pdf), [overview paper](https://paperswithcode.com/paper/an-overview-on-ieee-802-11bf-wlan-sensing-1))
- **Espressif esp-csi** ([espressif/esp-csi](https://github.com/espressif/esp-csi), Apache-2.0): Espressif's official CSI apps for ESP32, covering human detection and indoor positioning. It is the base layer most ESP32 CSI projects build on.
- Also seen: ESPectre, an ESP32 CSI motion detector with Home Assistant integration ([Hackaday, Jan 2026](https://hackaday.com/2026/01/28/make-your-own-esp32-based-person-sensor-no-special-hardware-needed/)), and Pulse-Fi, WiFi heart rate on ESP32 ([Hackaday, Sep 2025](https://hackaday.com/2025/09/05/heart-rate-monitoring-via-wifi/)).

### What the sources do and do not support about novelty
- **Not supported:** "none of them learn routines without labels". RuView's README claims routine and "what's normal" learning, and an on-device LLM.
- **Supported, as far as the sources go:**
  - None of the sources above describes an **embodied, physical responder**. RuView's robotics section is about giving robots sensing, not about a robot acting on an alert.
  - None of them describes **LLM explanations that cite the specific CSI evidence** behind each alert.
  - Origin does escalate to a caregiver, but through notifications only.
- **Safe pitch:** "camera-less CSI sensing (prior art: RuView, esp-csi, wifisense-pi, Origin) + per-room unsupervised baselines + Nemotron explanations that cite the sensor evidence + a robot lamp that physically checks in." Credit RuView explicitly.
