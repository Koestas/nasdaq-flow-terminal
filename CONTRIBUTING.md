# Contributing to Micro Futures Analyzer

Thanks for taking the time to contribute. MFA is actively developed and community input shapes what gets built.

---

## Running locally

**Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

No API keys required. Yahoo Finance data works out of the box.

---

## Reporting a bug

Use the **Bug Report** issue template. The more detail the better:
- What page / feature were you using?
- What did you expect to happen?
- What actually happened?
- Any error in the browser console or terminal?

---

## Requesting a feature

Use the **Feature Request** issue template. Describe the problem you're trying to solve, not just the solution. If it's based on an ICT concept or a specific coach's method, name it — context helps a lot.

---

## Submitting a pull request

1. Fork the repo and create a branch from `main`
2. Make your changes — keep them focused on one thing
3. Test it locally (run both backend and frontend)
4. Open a PR with a clear description of what you changed and why

Small, focused PRs get reviewed and merged faster than large ones.

---

## Code style

- **Backend:** Python, follow existing patterns in `routes/` and `engines/`
- **Frontend:** React functional components, Tailwind CSS, no class components
- No new dependencies without a good reason — keep the stack lean

---

## Questions?

Open a [Discussion](../../discussions) rather than an issue if you're not sure whether something is a bug or just a question.
