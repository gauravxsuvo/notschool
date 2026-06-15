# Notschool - Multi-Agent AI Learning Architect

Built for the **Google Gen AI Academy APAC 2026 Hackathon** - Track 1: Agentic AI

---

## Overview

Most AI educational tools are stateless question answering interfaces. Notschool OS is a fully automated, multi-agent pipeline that takes a single user goal and produces a complete, personalised, scheduled, resource-backed learning plan — without further input.

The system accepts a text goal or an image of a syllabus, textbook index, or job description. It reasons over that input, constructs a structured 7-day curriculum tailored to the learner's profile (age, existing skills, interests, preferred learning style), sources relevant video tutorials, surfaces real 2026 industry initiatives, persists the plan to a database, and books every study session directly into the user's Google Calendar — all in a single request.

Beyond generation, Notschool OS provides a full learning dashboard: progress tracking, streaks, per-module quizzes, an auto-rescheduler for missed sessions, and a context-aware multi-turn AI tutor that remembers prior conversations.

---

## Hackathon Criteria Alignment

| Criterion | Implementation |
|---|---|
| Primary Agent + Sub-Agents | LangGraph orchestrates four specialised agents: Architect, Librarian, Scheduler, and DB Saver. The Architect acts as the primary reasoning agent. |
| Store and Retrieve Structured Data | SQLite persists users, curricula, study sessions, quizzes, doubts, and chat threads. Stats, streaks, and quiz progress are computed at read time. |
| Integrate Tools via MCP | YouTube search and Google Calendar creation are exposed as MCP tools through a FastMCP server over stdio transport. |
| Multi-Step Workflow | Goal input → multimodal curriculum generation → resource retrieval → calendar scheduling → persistence — executed as a typed LangGraph state machine. |
| API-based System | All logic is served through a FastAPI backend with twenty-one REST endpoints covering auth (Google + guest), generation, dashboard, profile, quizzes, doubts, chats, and scheduling. |

---

## Key Features

- **Multi-modal curriculum generation.** Upload a photo of a syllabus or job description; the Architect agent extracts topics and produces a structured 7-day plan.
- **Profile-aware personalisation.** Per-user profile (display name, age, skills, interests, learning style) is fed into both the curriculum generator and the AI tutor so output is calibrated to the learner.
- **Guest mode for zero-friction evaluation.** Evaluators without a Google account can launch a sandbox session in one click. A warning modal lists exactly what works (roadmaps, quizzes, tutor, dashboard, profile) and what doesn't (Google Calendar sync, email reminders), and surfaces a copyable test account for anyone who wants the full Calendar flow. Guest sessions are authenticated with HMAC-signed tokens — no Google scope is requested or stored.
- **Auto-scheduling on Google Calendar.** Every module becomes a calendar event using the user's OAuth token, sized by the module's `duration_hours` and clamped to one minute below the cadence so consecutive sessions never overlap (a 1-hour cadence with 1-hour modules generates 59-minute events, not back-to-back collisions).
- **Configurable cadence.** At generation time the user picks how far apart consecutive modules sit — `N min`, `N hour`, `N day`, or `N week`. Short cadences power live demos (a 5-minute cadence lets the auto-rescheduler be observed end-to-end without waiting a day); long cadences match a real study schedule. The roadmap chart, planner, and dashboard all relabel and reformat per cadence — `Day 1` for daily plans, `Slot 1` with the actual clock-time for sub-day plans, and `Wk 1` for weekly plans — so the timeline always matches reality.
- **Push-forward auto-rescheduling.** When the active module's window elapses without being marked done, that module slides into the next slot, the next module slides one slot further, and so on — preserving the original spacing. The Calendar event is patched in place (not deleted and recreated) so reminders persist. The dashboard polls on a cadence-aware interval (twice per cadence, clamped to 20s–5min) so a 5-min demo reschedule fires within ~2.5 minutes of the miss.
- **Sequential completion.** A module can only be marked done once every earlier module is finished. The lock is enforced both in the UI (subsequent rows render a "Locked" button) and on the backend (HTTP 409 with a clear message), so the order can't be bypassed via direct API calls.
- **Per-module quizzes.** Five-question multiple-choice quizzes are generated on demand, scored, persisted, and aggregated into accuracy and points-earned metrics.
- **Multi-turn AI tutor.** Context-aware chat threads scoped to a curriculum or specific module. Prior turns are replayed into the prompt so follow-up questions resolve correctly.
- **Industry initiatives panel.** Real 2026 cohorts, bootcamps, and certifications from Google, Amazon, Microsoft, and others — filtered by provider and de-duplicated.
- **Custom roadmap visualisation.** A bespoke timeline chart showing day badges, status colours (done / up-next / overdue), and on-hover module descriptions for a clean at-a-glance read with detail one hover away.
- **Dashboard analytics.** Day streak (current and best), weekly velocity, completion percentage, and quiz accuracy.
- **Light and dark themes**, system-preference aware, with a one-click toggle.
- **Mobile-first responsive UI.** Every view — from the generator form to the planner action grid to the AI tutor — has been designed to work cleanly on phones as well as desktops. The layout adapts at 480/640/768 px breakpoints, all interactive controls hit the 44 × 44 px touch-target minimum, modals slide up as bottom sheets, the AI tutor's chat list opens as an overlay drawer on small screens, and form inputs use a 16 px font so iOS Safari does not auto-zoom on focus. The viewport respects the iPhone safe-area inset so the floating "Ask a doubt" FAB never sits under the home-indicator gesture bar. `prefers-reduced-motion` is honored throughout.

---

## System Architecture

The pipeline is implemented as a directed LangGraph state machine. Each node is a stateless function that reads from and writes to a shared `NotschoolState` TypedDict. The graph executes linearly:

```
[User Request + Profile]
        |
        v
   Architect          Multimodal curriculum generation via Gemini.
        |              Accepts text or image input. Returns a structured
        |              7-day JSON plan with topics, durations, search
        |              queries, certifications, and 2026 initiatives.
        |              Personalisation context (age, skills, interests,
        |              learning style) is injected into the prompt.
        v
   Librarian          Resource curation. Queries the YouTube Data API
        |              for one tutorial video per module using the
        |              Architect's search queries.
        v
   Scheduler          Reads the curriculum and creates a Google Calendar
        |              event for every module using the user's OAuth
        |              token. Event durations come from the curriculum
        |              JSON. Failures per session are surfaced to the
        |              client as a calendar_status object.
        v
   DB Saver           Persists the curriculum row and one study_session
        |              row per module to SQLite, including event ids and
        |              video URLs for later use by the rescheduler.
        v
[Final state returned to FastAPI]
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph |
| LLMs | Gemini (via `google-genai` SDK) — used by Architect, quiz generator, and AI tutor |
| Backend | FastAPI + Uvicorn |
| Frontend | HTML5, Tailwind CSS (CDN), Vanilla JS — single-page app with no build step. Mobile-first responsive layout, safe-area aware, with a custom in-app confirmation dialog (no native `confirm()` popups). |
| Database | SQLite3 |
| Tool Integration | Model Context Protocol (MCP) over stdio via FastMCP |
| External APIs | YouTube Data API v3, Google Calendar API (OAuth 2.0), Google Identity (OAuth) |
| Web Search | DuckDuckGo Search (`duckduckgo-search`) |
| Resilience | Tenacity-based exponential backoff for Gemini 503/429 responses, per-module Calendar fallback |
| Deployment | Google Cloud Run (Dockerfile included) |

---

## Agents

### Architect — `agents/architect_node.py`
The primary reasoning agent. Calls Gemini with either a text prompt or a multimodal prompt containing an uploaded image. Injects the learner's profile (name, age, existing skills, interests, preferred style) as personalisation context. Returns a normalised JSON curriculum: seven daily modules, YouTube search queries, certifications, and a hand-anchored set of real 2026 industry initiatives from Google, Amazon, Microsoft, and other providers. Includes a fallback initiatives library so the panel always renders credible programs even if Gemini is rate-limited.

### Librarian — `agents/librarian_node.py`
The resource curation agent. Reads `search_queries` from the Architect's output and calls the YouTube Data API to retrieve one tutorial video per query. Results are stored alongside the corresponding session so the planner can render a "Watch video" button per module.

### Scheduler — `agents/scheduler_node.py`
The calendar agent. Uses the user's OAuth 2.0 access token (passed at request time, never stored server-side) to create a Google Calendar event per module. Event duration is derived from the module's `duration_hours` field, then clamped to `cadence − 1 minute` so consecutive events never overlap on tight cadences (a 1-minute demo creates 1-minute events; a 1-hour cadence with 1-hour modules creates 59-minute events). For sub-day cadences the first event starts ~1 minute after generation so the rescheduler can be observed end-to-end; for day/week cadences each module anchors to a 10:00 local-time slot. If the access token is missing (guest mode) or revoked, the step is skipped gracefully and a `calendar_status` object surfaces the gap to the frontend.

### DB Saver — `agents/db_node.py`
The persistence agent. Writes the curriculum row plus one `study_sessions` row per module, including goal, module name, scheduled timestamp, calendar event id, calendar link, and YouTube URL. These rows are later read by the dashboard, the planner, and the rescheduler.

---

## API Endpoints

All authenticated endpoints expect a `Bearer` token in the `Authorization` header. The token can be either:

- A Google OAuth access token (full features, including Calendar sync), or
- An HMAC-signed guest token issued by `/api/auth/guest` (Calendar features skipped; everything else works).

The same `_require_user` dependency handles both shapes — Google tokens are validated against Google's userinfo endpoint, guest tokens are verified by recomputing the signature with the server's `GUEST_TOKEN_SECRET`.

### Auth and profile
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/verify` | Verifies the bearer token (Google access token *or* HMAC-signed guest token), registers/updates the user, and returns the profile. |
| `POST` | `/api/auth/guest` | Issues a fresh guest identity + HMAC-signed token. No body required. Calendar features stay disabled for the resulting session. |
| `GET` | `/api/profile` | Returns the user's personalisation profile. |
| `PUT` | `/api/profile` | Updates display name, age, skills, interests, and learning style. |

### Curriculum and dashboard
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/generate` | Triggers the full LangGraph pipeline. Accepts `goal`, optional `image` file, and optional `timeframe_amount` + `timeframe_unit` (`min` / `hour` / `day` / `week`) to control the spacing between consecutive modules. Defaults to one module per day. |
| `GET` | `/api/dashboard` | Returns curricula list, aggregate stats, streak, and the next pending session. |
| `GET` | `/api/curriculum/{id}` | Full curriculum, sessions, and quiz stats for a single roadmap. |
| `DELETE` | `/api/curriculum/{id}` | Deletes a curriculum and removes all linked calendar events. |

### Sessions and rescheduling
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/session/complete` | Marks a session done and removes its calendar event. |
| `POST` | `/api/reschedule` | Detects missed sessions and re-books each on the next free 10am slot. |
| `POST` | `/api/reset` | Clears the logged-in user's data and removes their calendar events. |

### Quizzes
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/quiz/generate` | Generates or returns the cached quiz for a module. `force=true` regenerates. |
| `POST` | `/api/quiz/submit` | Records the score for a quiz attempt. |

### AI tutor (multi-turn chats)
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/doubt/ask` | Asks the tutor a question. Creates a new chat thread if `chat_id` is omitted. |
| `GET` | `/api/chats` | Lists chat threads, optionally scoped to a curriculum. |
| `POST` | `/api/chats` | Creates an empty chat thread. |
| `GET` | `/api/chat/{id}` | Returns a chat thread with ordered messages. |
| `DELETE` | `/api/chat/{id}` | Deletes a chat thread and its messages. |
| `POST` | `/api/chat/{id}/rename` | Renames a chat thread. |
| `GET` | `/api/doubts` | Legacy flat doubts list for backward compatibility. |

### System
| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the frontend (`index.html`). |
| `GET` | `/api/health` | Cheap readiness probe. Reports which API keys are configured. |

---

## Database Schema

| Table | Purpose |
|---|---|
| `users` | OAuth-linked user record plus profile fields (display name, age, skills, interests, learning style). |
| `curricula` | One row per generation. Stores the full curriculum JSON, YouTube URLs, opportunities, and web trends. |
| `study_sessions` | One row per module. Tracks `scheduled_time`, `status`, `event_id`, `event_link`, `youtube_url`, and `completed_at`. |
| `quizzes` | Generated quizzes, scored on submission. |
| `chats` | Chat thread metadata for the AI tutor. |
| `doubts` | Individual question/answer turns linked to a chat. |

All migrations are idempotent (`_add_column_if_missing`), so the schema evolves without manual intervention between deployments.

---

## Project Structure

```
notschool/
├── main.py                   FastAPI application, routes, and request orchestration
├── auth.py                   OAuth helpers
├── requirements.txt
├── Dockerfile                Cloud Run container definition
├── .env                      Environment variables (not committed)
│
├── core/
│   ├── config.py             Environment validation on startup
│   ├── graph.py              LangGraph state machine definition and compilation
│   └── state.py              NotschoolState TypedDict schema
│
├── agents/
│   ├── architect_node.py     Curriculum generation agent (Gemini, multimodal, profile-aware)
│   ├── librarian_node.py     Resource curation agent (YouTube)
│   ├── scheduler_node.py     Google Calendar scheduling agent
│   └── db_node.py            SQLite persistence agent
│
├── tools/
│   ├── mcp_server.py         FastMCP server exposing YouTube and Calendar tools
│   ├── youtube_client.py     YouTube Data API v3 wrapper
│   ├── calendar_client.py    Google Calendar API OAuth wrapper
│   ├── auth_client.py        Google access-token verification
│   ├── guest_auth.py         HMAC-signed guest tokens for the no-Google evaluator flow
│   ├── gemini_client.py      Gemini SDK wrapper with model fallback and retries
│   ├── quiz_generator.py     Quiz generation via Gemini
│   └── doubt_resolver.py     Multi-turn AI tutor with profile and history context
│
├── db/
│   ├── schema.py             SQLite schema initialisation and migrations
│   └── crud.py               Database read/write operations
│
└── frontend/
    └── index.html            Single-page UI (Tailwind CDN, Vanilla JS, custom roadmap chart)
```

---

## Setup

### Prerequisites

Obtain credentials for the following:

- **Gemini** — Google AI Studio API key.
- **YouTube Data API v3** — API key from the Google Cloud Console.
- **Google OAuth 2.0** — Client ID for an authorised JavaScript origin matching the deployment URL. The Calendar API must be enabled on the same Cloud project.

### Local installation

1. Clone the repository:
   ```bash
   git clone https://github.com/cinexg/notschool-os.git
   cd notschool-os
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   YOUTUBE_API_KEY=your_youtube_api_key
   GOOGLE_CLIENT_ID=your_oauth_client_id
   GOOGLE_CLIENT_SECRET=your_oauth_client_secret

   # Optional but strongly recommended in any shared deployment — used to sign
   # guest tokens. Falls back to a baked-in dev secret if unset, which means
   # guest tokens issued by one server instance would also validate on another
   # instance using the default; set this to a random ≥32-char string in prod.
   GUEST_TOKEN_SECRET=replace_with_a_long_random_string
   ```

4. Update the `client_id` in `frontend/index.html` to match your OAuth Client ID, and (optionally) replace the placeholder test-account credentials shown in the guest-mode warning modal with the real shared evaluation account email/password.

5. Start the server:
   ```bash
   uvicorn main:app --reload
   ```

6. Open `http://localhost:8000`. Sign in with Google for the full experience, or click **Continue as Guest** to launch a sandbox session immediately. Either way, completing your profile lets the AI personalise your roadmap.

### Cloud Run deployment

The application is designed for containerised deployment. The provided `Dockerfile` builds an image that binds Uvicorn to the `PORT` environment variable. Configure all keys as Cloud Run secrets or environment variables, and add the Cloud Run URL as an authorised JavaScript origin on the OAuth Client.

---

## Personalisation Flow

When a user signs in for the first time the dashboard nudges them to complete their profile. The profile is then injected into two prompts:

1. **Architect prompt** — the learner's age, existing skills, interests, and preferred style appear as a `Personalisation context` block, asking the model to calibrate vocabulary, examples, and pacing accordingly.
2. **AI tutor prompt** — the same fields are passed to `resolve_doubt`, so the tutor pitches answers at the right level and weaves in the learner's interests when natural.

Profile updates are persisted on the user row and take effect on the next generation or doubt request — no regeneration of existing roadmaps is required.

---

## Key Design Decisions

**Why LangGraph over a simple function chain?**
LangGraph provides a typed shared state (`NotschoolState`) that flows through every agent, making the data contract explicit and auditable. Each node function is independently testable, and adding a new agent is a matter of registering a node and an edge.

**Why MCP for tool integration?**
Exposing tools via the Model Context Protocol decouples implementations from agent logic. The same MCP server can be connected to any MCP-compatible client, making the toolset reusable outside this pipeline.

**Why per-request OAuth tokens instead of server-stored credentials?**
The user's Google access token is passed with each request and used transiently. The server never stores or caches Google credentials, eliminating an entire class of token-management failure modes and keeping the architecture stateless.

**Why HMAC-signed guest tokens instead of a database session table?**
Evaluators need a one-click way to try the product without surrendering a Google account, but the rest of the system already runs stateless on per-request tokens. A signed token over `guest_<id>` matches that model exactly: the server can authenticate any guest by recomputing the signature with `GUEST_TOKEN_SECRET`, no session lookup table, no expiring rows to garbage-collect. Tampering invalidates the signature, and rotating the secret instantly revokes every outstanding guest token at once.

**Why a custom roadmap chart instead of Mermaid?**
The earlier Mermaid graph rendered as a tiny vertical chain that was hard to read on mobile and failed to surface module status, descriptions, or duration. The bespoke timeline chart renders the same information in a single glance, integrates session state (done / up-next / overdue), and animates in for visual polish — without pulling in a 1MB dependency. On phones the chart shrinks the day-circle, drops the hover-only description into a permanently-visible block, and stacks the status badges below the topic so a 360 px screen still reads cleanly.

**Why a custom confirmation dialog instead of `window.confirm()`?**
Native `confirm()` popups are jarring inside a full-screen webapp, particularly on iOS where the system dialog visually breaks out of the app's chrome. A small in-app dialog (`showConfirm()`) styled to match the rest of the design lets us add a clear destructive-action red, distinct verbs ("Delete" vs "Confirm"), explanatory body copy, and a friendlier bottom-sheet animation on phones. The same primitive is used for roadmap deletion, quiz regeneration, unanswered-quiz submission warnings, and chat thread deletion.

**Why the action grid renders as `4 + 1` on phones?**
The planner row exposes five actions per session — Video, Calendar, Quiz, Doubt, and Mark done. On desktop a five-column row reads like a menu. On phones five buttons in two columns produced a lopsided grid (3 + 2) and the most important action — Mark done — fell into the second column where it competed with secondary actions. The mobile layout collapses the four secondary actions to icon-only in one row of four, and gives Mark done a full-width row of its own. The primary CTA is always reachable with a single thumb.

**Why DuckDuckGo Search instead of Google Search?**
The `googlesearch-python` library scrapes Google directly and is rate-limited aggressively (HTTP 429) on shared cloud IPs. The `duckduckgo-search` library uses an unofficial API that is not subject to the same restrictions and does not require an API key.

**Why fallback initiatives are hand-curated?**
Gemini occasionally hallucinates URLs or fabricates programs that no longer exist. A vetted fallback set of real 2026 cohorts from Google, Amazon, and Microsoft guarantees the Industry Initiatives panel always renders credible programs, even when the live model output is rate-limited or thin.
