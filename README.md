# AI Health Companion - Backend MVP

Nutrition and wellness companion (not a doctor). FastAPI modular monolith. **Backend only so far** - no mobile/web app yet.

## Run

```bash
cd backend
pip install -e ".[dev]"
pytest -q                                   # 94 tests
HC_ENV=dev HC_JWT_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(48))") \
  uvicorn app.main:get_app --factory --reload   # SQLite + auto-seed; docs at /docs
```
Postgres: `cp .env.example .env`, fill secrets, `docker compose up` (Dockerfile not yet build-tested).

## What exists

| MVP item | Where | Status |
|---|---|---|
| Auth + consent | `api/v1/auth_users.py` | done (JWT, bcrypt, consent stored, account erasure) |
| User profile / conditions / allergies | same | done |
| Barcode scan + product DB | `domain/barcode.py`, `services/catalog.py` | done; **8 demo products only** |
| Nutrition engine | `domain/nutrition.py` | done, deterministic, None != 0 |
| Ingredient + additive analysis | `domain/ingredients.py`, `data/additives.json` | done (EN/Hindi, INS, allergens, NOVA estimate) |
| Label OCR | `/scan/label`, `/scan/label-text` | pipeline done; **OCR engine not plugged in** (text endpoint works) |
| Health score + personal compatibility | `domain/scoring.py`, `domain/compat.py` | done, configurable, explained |
| 50-100 Indian foods | `data/foods.csv` | **71 foods, approximate, unverified** |
| Food photo recognition | `/scan/food-photo` | pipeline + corrections flywheel done; **no vision model plugged in** |
| Basic chatbot | `ai/orchestrator.py` | done: safety -> tools -> deterministic draft -> optional LLM rewrite -> validator |
| Basic recommendations | `services/recommendations.py` | done, rule-based |
| Daily dashboard | `/nutrition/today` | done |
| AI Gateway | `ai/providers.py` | LLM/Vision/OCR interfaces; mock + Anthropic adapter (adapter untested live) |

## Safety design
- Emergencies, self-harm, eating disorders, crash diets and medication dosing are answered with static text; the LLM is never called.
- LLM output (when enabled) is only a tone rewrite of a deterministic draft. Replies with numbers not in the verified facts, diagnosis wording, or medication advice are discarded.
- Every score/rule cites a source and carries a `NEEDS_CLINICAL_REVIEW` status.

## Must-do before real users
1. **Replace seed nutrition values** with IFCT 2017 / verified data (licence check). Today everything is flagged `verified: false` and responses say so.
2. **Clinical/dietitian review** of `scoring_config.json`, `guidelines.json`, `targets_config.json`, `additives.json` (placeholders, see `status`).
3. Alembic migrations (prod refuses to auto-create tables, but no migrations exist yet).
4. Rate limiting, login lockout, refresh tokens, email verification, password reset.
5. Encryption at rest + secrets manager + retention policy; privacy/consent text reviewed for India's DPDP Act.
6. Real OCR and vision providers, then golden-dataset accuracy tests.

## Android app (`mobile/`)
Expo (React Native, TypeScript). Screens: login/register, Home (daily dashboard), Scan (barcode camera + dish search), Ask (chat), Profile.
The server address is set on the login screen (default `http://10.0.2.2:8000` = the host machine from an Android emulator).
The app allows plain HTTP for development; **use HTTPS before release**.

Build the APK in the cloud: push to GitHub, and the `android-apk` workflow publishes `health-companion.apk` under the repo's Releases.
Locally (needs Android SDK + JDK 17): `cd mobile && npm ci && npx expo prebuild --platform android && cd android && ./gradlew assembleRelease`.
Not yet built or run on a device by me.
