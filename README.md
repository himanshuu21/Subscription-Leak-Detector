# Subscription Leak Detector

## What it does
The Subscription Leak Detector is a financial tool designed to help users identify and manage their recurring payments. Many people lose track of their subscriptions, resulting in ongoing charges for services they no longer use. This project provides a simple way to upload transaction histories and automatically detect active subscriptions.

By identifying hidden subscriptions and highlighting sneaky price hikes, the tool empowers users to take control of their spending. It provides a clean dashboard displaying annual spend projections, confidence scores for detected subscriptions, and actionable insights to cancel unwanted services.

The dashboard is a planning tool. “Mark to cancel” records an intention and calculates projected savings; it does not cancel a merchant account or payment mandate without a future provider-specific integration.

## Why it's non-trivial
Detecting subscriptions from raw bank transaction data is a challenging problem for several reasons:
- **Noisy Merchant Strings**: Real-world transaction descriptions are messy (e.g., `NETFLIX.COM 8X4F2` vs `NETFLIX INC #4471`). Grouping them correctly requires fuzzy matching.
- **Date Drift**: Recurring charges rarely occur on the exact same day each month. Weekends, holidays, and bank processing times introduce random jitter (date drift) into the transaction dates.
- **Price Hikes vs. New Subscriptions**: Distinguishing a legitimate price increase for an existing subscription from a completely new service requires analyzing the persistence and timing of the amount drift.

## Detection Pipeline
The subscription detection pipeline consists of 4 main stages:
1. **Merchant Normalization**: Cleans descriptions, resolves audited aliases, deduplicates normalized names, and fuzzy-compares only names sharing a token/prefix block. This removes the previous all-row O(n²) comparison.
2. **Periodicity Detection**: Requires at least 70% of intervals to match a weekly, monthly, or yearly cycle and rejects implausibly dense merchant activity. At least three charges are required.
3. **Amount-Drift Detection**: Examines changes in charge amounts over time. Uses a 2% noise threshold to ignore minor currency fluctuations while detecting persistent price hikes (requires persistence=2).
4. **Confidence Scoring**: Combines periodicity (0.45), merchant matching (0.35), and amount stability (0.20). Results below the 0.75 minimum confidence threshold are not persisted.

## Evaluation

Run the labeled sample evaluation with:

```bash
python scripts/evaluate.py
```

Current evidence-supported result: precision **1.00**, recall **1.00**, F1 **1.00**, zero false positives, and zero false negatives across the six truth labels with at least three observations. Dropbox and Hotstar each have one observation and are reported as `insufficient_evidence`, not silently removed or guessed from a merchant allow-list.

## Financial data and security

- Money is parsed and stored as fixed-point `Decimal`/`NUMERIC(14,2)`.
- Debit and credit columns are handled separately; credits never become expenses.
- Upload diagnostics retain total, imported, credit, and invalid-row counts plus the first 50 row errors.
- Uploads are bounded to 5 MiB by default.
- Passwords require 12–128 characters; login attempts are rate limited.
- Google OpenID Connect uses the server-side authorization-code flow and links only verified Google email addresses.
- Browser authentication uses Secure (in production), HTTP-only, SameSite=Strict cookies instead of local storage.
- Production startup rejects missing/short secrets and runs without reload mode or source mounts.

## Tech Stack
| Component | Technology | Why |
| --- | --- | --- |
| Backend | FastAPI | Fast, async, built-in validation, excellent for API development |
| Frontend | React + Vite | Component-based single-page UI with client-side routing |
| Styling | Custom responsive CSS | A focused design system with no runtime CSS dependency |

## Getting Started (Local Dev)
```bash
# SQLite (no Docker)
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal, start the React development server (it proxies API calls to FastAPI):

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. To serve the production React bundle directly from FastAPI, run `npm run build` first and open `http://localhost:8000`.

## Getting Started (Docker)
```bash
docker-compose up --build
```

## Enable Google sign-in

1. In Google Cloud Console, configure the OAuth consent screen.
2. Create an OAuth 2.0 Client ID with application type **Web application**.
3. Add the local authorized redirect URI matching the address you use:

   ```text
   http://127.0.0.1:8000/api/auth/google/callback
   http://localhost:8000/api/auth/google/callback
   ```

4. Add the credentials to `.env`:

   ```env
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   ```

5. Restart Uvicorn. The **Continue with Google** button appears automatically.

For production, register `https://your-domain/api/auth/google/callback` as a separate authorized redirect URI and set both environment variables in the hosting dashboard. Redirect URIs must match exactly; keep the client secret server-side and out of source control.

## Generating Test Data
```bash
python data/generator/generate.py --output sample.csv --months 12
# Then upload sample.csv via the UI
```

## Running Tests
```bash
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest --cov=app/core --cov-report=term
python scripts/evaluate.py
```

## Local demo credentials

After `alembic upgrade head`, run `python scripts/create_demo_user.py`. In development only, this creates:

- Email: `demo@example.com`
- Password: `DemoPassword!2026`

Production requires an explicit `DEMO_PASSWORD`; never reuse the local password on a public deployment.

## Deployment and evidence

`render.yaml` and the production-hardened Docker image make the app ready for a Render deployment. Set database credentials and a 32+ character secret, deploy, then verify `/health` and `/docs`. Supporting artifacts are in [API docs](docs/API.md), [architecture](docs/ARCHITECTURE.md), and the [two-minute demo script](docs/DEMO.md). Add screenshots under `docs/screenshots/` and record the script only after a real public URL exists, so portfolio evidence is verifiable rather than fabricated.

## Project Structure
```text
├── app/
│   ├── main.py
│   ├── core/           # Subscription detection logic
│   ├── api/            # API endpoints
├── frontend/           # React + Vite single-page application
│   └── src/            # Pages, API client, and responsive styling
├── data/
│   └── generator/      # Synthetic data generation script
├── tests/              # Unit and integration tests
└── README.md
```

## Interview Notes
- **Why rule-based + statistical, not ML?**: For this specific problem, explainability is crucial. Users need to know *why* a set of charges was flagged as a subscription. A statistical approach provides clear confidence scores based on explainable factors, whereas ML models can be black boxes and require significant labeled training data.
- **Why rapidfuzz token_sort_ratio at threshold 85?**: `token_sort_ratio` ignores word order, which is perfect for transaction strings where merchant names and metadata get shuffled (e.g., `AMAZON PRIME` vs `PRIME AMAZON`). A threshold of 85 provides a good balance between catching true matches and avoiding false positives.
- **Why blocked matching + union-find?**: Blocking limits fuzzy candidate generation to names sharing a deterministic key; union-find then retains transitive clustering. Worst-case complexity can still approach O(u²) in one pathological block, where `u` is unique normalized names, so the implementation does not claim unconditional O(n log n).
- **Why require interval coverage?**: A matching median can be produced by mostly irregular activity. Requiring 70% of individual intervals to fall within the cycle tolerance makes the decision explainable and prevents accidental matches such as Swiggy in the sample.
- **Why 2% noise threshold for drift?**: Small fluctuations often occur due to currency conversion rates or minor bank fees. A 2% threshold filters out this noise while still capturing legitimate price hikes.
- **Why weights periodicity > merchant > amount?**: Timing (periodicity) is the strongest signal of a subscription. Merchant similarity is a strong secondary signal, while amount stability is the weakest because prices do change and variable-rate subscriptions exist.

## Scope and Future Work
- **Out of Scope (v1)**: Direct bank integrations (e.g., Plaid), machine learning models for classification, full budgeting features.
- **Future Work**: Adding support for variable-amount subscriptions (e.g., utility bills), multi-currency handling, and proactive alerts for upcoming renewals.

## Résumé description

Built a deployment-ready FastAPI subscription-leak detector that normalizes noisy bank descriptors with alias-aware blocked fuzzy matching, validates recurring cycles using interval coverage, and detects persistent price hikes with fixed-point financial arithmetic; achieved 1.00 precision/recall/F1 on the evidence-supported labeled sample, and added Google OpenID Connect, secure cookie auth, rate limiting, bounded uploads with row-level diagnostics, background analysis, indexed pagination, Docker deployment configuration, and GitHub Actions CI.
