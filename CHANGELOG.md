# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Live mission-control UI: animated agent graph, streaming thoughts, per-agent
  inspector drawer, live metrics, run history with replay, and deliverable
  export (Markdown) plus full event-trace export (JSON).
- Multi-provider support with an in-app model picker (offline, Google Gemini,
  OpenAI) and a live key-configured indicator. Any OpenAI-compatible model works.
- Intent triage: greetings and small talk get a single quick reply instead of a
  full multi-agent run, saving calls and free-tier rate limit.
- Centralised typed `Settings`, structured JSON logging, and a `.env` loader.
- Reliability guards: bounded run store, per-run timeout, and a concurrent-run
  cap (returns `503` when busy).
- Rate-limit resilience: retry with exponential backoff on `429`/`5xx`
  (honouring `Retry-After`) and a concurrency cap on upstream calls.
- Accessibility: keyboard-navigable agent nodes, visible focus, `aria-live`
  status, and a reduced-motion path. WebSocket auto-reconnects and replays on
  drop.
- Typed OpenAPI surface, `py.typed`, CI on Python 3.10 to 3.13 with lint, format
  check, type check, and a coverage gate.

## [0.1.0]

- Initial release.
