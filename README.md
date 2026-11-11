# ShadeMaper (v0.9.0-beta)

**ShadeMaper** is a desktop reconnaissance, attack surface mapping, and lightweight heuristic vulnerability analysis platform. Instead of relying on linear HTTP crawling, the application orchestrates distributed asynchronous workers, browser-level TLS impersonation, statistical timing analysis, and hardware-accelerated WebGL graph rendering to map web infrastructure in real time.

The system was architected, implemented, and covered with automated tests entirely solo.

---

## Interface & Live Visualization

![ShadeMaper Main Interface](https://github.com/user-attachments/assets/66f64e1d-b2a1-48c5-bcb3-3d313c912c60)

![ShadeMaper Graph View](https://github.com/user-attachments/assets/19581ff8-fd8a-4e68-ade3-31ce8963461b)

![ShadeMaper Console Logs](https://github.com/user-attachments/assets/e34a1c9f-8084-40e3-a447-29941e0a230d)

*Visualization of public endpoints mapped during authorized reconnaissance testing (WebGL node graph and live event console).*

---

## Architectural Deep Dive

Unlike basic single-threaded crawlers, ShadeMaper decouples the graphical user interface, network I/O, and CPU-bound heuristic calculations across isolated execution contexts:

* **Hybrid Event Loop Architecture (`PySide6` + `qasync`):** Integrates Qt's main GUI thread with Python's `asyncio` event loop. This prevents UI freezes while hundreds of concurrent network coroutines, log streams, and WebGL canvas updates execute simultaneously.
* **Distributed Task Broker & State Management (`Redis`):** Uses Redis in-memory data structures (`task_queue`, `visited`, `scheduled_queue`) with connection keep-alive and automatic retry policies to coordinate asynchronous worker pools, guarantee URL deduplication, and prevent cyclic crawling traps.
* **CPU-Bound Offloading (`ProcessPoolExecutor`):** Isolates heavy heuristic scoring and payload analysis tasks into separate worker processes, bypassing Python's Global Interpreter Lock (GIL) so network coroutines remain non-blocking.
* **Hardware-Accelerated Graph Engine (`VivaGraphJS` + `Chromium`):** Embeds a Chromium engine via `QWebEngineView` to render large node networks via WebGL. Graph traversal algorithms compute and highlight the shortest paths from the root domain to vuln  endpoints within 20–30 seconds of scanning if target has them.

---

## Core Security & Evasion Modules

* **Stealth & TLS Fingerprint Impersonation (`StealthEngine`):** Built on `curl_cffi` (`chrome120` impersonation) to replicate legitimate browser TLS handshakes (JA3/JA4) and HTTP/2 frame structures, bypassing basic bot-mitigation checks from Cloudflare, AWS WAF, and Akamai.
* **Behavioral Simulation & Load Control (`BehavOptimize` & `AdaptRatelimiter`):**
  * Dynamically rotates `User-Agent` and `Referer` headers per request while injecting randomized delays and background static asset requests (`.css`, `.ico`, `.js`) to mimic organic user traffic.
  * Implements an AIMD-style adaptive rate limiter alongside a **Circuit Breaker** that automatically pauses requests to domains returning `429` or `503` status codes.
* **Dynamic Payload Obfuscation (`PayloadHider`):** Mutates injection vectors on the fly using Hex, Unicode, Double URL-encoding, null-byte injection (`%00`), and inline SQL/comment noise (`/*--!*/`) to evade signature-based WAF rules.
* **Statistical Timing Anomaly Detection (`ResonanceDetector`):**
  * Tracks historical response latencies per endpoint and applies **Z-score statistical analysis** (mean and standard deviation) to detect blind time-based anomalies without triggering false positives on network jitter.
  * Executes an automated **`doublecheck` validation routine**: when an anomaly is flagged, the engine dynamically mutates the payload's delay parameter (e.g., scaling `SLEEP(4)` to `SLEEP(9)`) and re-tests the endpoint to confirm proportional server latency.
* **Weighted Soft-404 Heuristic Engine:** Evaluates HTTP responses using a multi-factor scoring system (HTML structural tags, content-type validation, and regex key-value matching) to filter out custom `200 OK` error pages and accurately identify exposed `.env`, `.git/config`, and backup files.
* **DOM Discovery & Hidden Route Prediction (`DomScaner` & `PhantomNodedetector`):** Uses headless browser rendering (`Playwright`) to trigger dynamic UI elements and extract hidden query parameters, combined with heuristic path prediction for unlinked endpoints.

---

## Technology Stack

* **Core & Concurrency:** Python 3.11+, `asyncio`, `concurrent.futures` (`ProcessPoolExecutor`), `multiprocessing`
* **GUI & Graphics:** `PySide6` (Qt for Python), `qasync`, `QWebEngineView`, `VivaGraphJS` (WebGL)
* **Message Broker & Caching:** `Redis` (with automatic failover/retry configuration)
* **Networking & Stealth:** `curl_cffi` (BoringSSL / TLS impersonation), `fake-useragent`
* **Parsing & Headless DOM:** `BeautifulSoup4`, `Playwright`
* **Quality Assurance:** `pytest` (unit and integration test suites for asynchronous workers and detectors)

---

## Installation & Quick Start

### Prerequisites
* Python 3.11+
* Running local **Redis** server (`127.0.0.1:6379`)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com
   cd ShadeMaper
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Linux / macOS:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python run.py
   ```

---

## Project Status & Known Limitations

The project is currently at **`v0.9.0-beta`** and is maintained as a showcase of system architecture and application security engineering. Core components are complete and tested, though minor edge-case issues may occur under extreme concurrency:

* **Anti-Bot & Proof-of-Work Challenges:** The scanner does not currently support websites protected by strict anti-bot gates requiring JavaScript challenge solving or human-verification cookies (e.g., CAPTCHA / "Verify you are human" interstitials).
* **DOM Context Isolation:** The headless DOM click emulator operates in an isolated context and does not synchronize dynamic session cookies back into the `curl_cffi` connection pool.
* **SPA Query Mutations:** Deep fuzzing of complex Single Page Applications (SPAs) may occasionally pass malformed dynamic query parameters.

Bug fixes, architectural improvements, and feature suggestions are welcome via **Pull Requests**.

---

## Disclaimer

This software was developed strictly for educational purposes, authorized security auditing, and architectural demonstration. Do not use this tool against targets without explicit written permission from the infrastructure owner.
