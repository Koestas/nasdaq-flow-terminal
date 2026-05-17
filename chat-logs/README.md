# Chat Logs

Claude Code conversation transcripts — saved for reference.

| File | Session | Size |
|------|---------|------|
| session-2026-05-17-current.jsonl | May 17 2026 — Backtest + Confluence + native futures fixes | 2.7 MB |
| session-2026-05-17-earlier.jsonl | May 17 2026 — earlier context (ICT engine, coaching narrative, stop direction fixes) | 2.1 MB |

**Last code push:** `5090a12` — Add Signal Backtest engine + Multi-TF Confluence panel  
**Pushed:** 2026-05-17 ~19:50 UTC

## How to read

Each `.jsonl` file is one JSON object per line. To pretty-print a single turn:
```bash
cat session-2026-05-17-current.jsonl | python3 -c "import sys,json; [print(json.dumps(json.loads(l), indent=2)) for l in sys.stdin]" | less
```
