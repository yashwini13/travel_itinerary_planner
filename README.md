# 🧭 Personalized Travel Itinerary Planner

Skill Wallet Capstone Project 4. A Streamlit app that recommends destinations, builds day-by-day itineraries with geographic clustering and live budget tracking, lets you swap activities, and exports an offline PDF guide.

**Live demo:** _add your Streamlit Community Cloud link here_

## Features

| Module | What it does |
|---|---|
| **Configuration** | Secure API key input (Gemini or Groq), demo mode with no key, full trip preference form (destination or vibe, duration, dates, budget, party, pace, interests, vegetarian option) |
| **Tab 1: Recommender** | Top 3 matching cities based on budget, travel-month season and mood, with highlight tags and match score |
| **Tab 2: Itinerary** | Day-wise plan with 4 time slots (Morning Sightseeing, Lunch, Afternoon Leisure, Evening Dining & Entertainment), one neighbourhood per day to avoid backtracking, approximate transit distance, itemized costs in local currency, USD and INR, and a running cumulative budget chart |
| **Tab 3: Customize** | Swap a single activity (e.g. "Swap museum for outdoor market", "Find vegetarian lunch spot") or regenerate one day without touching the rest |
| **Tab 4: Trips & PDF** | Save multiple trips, view trip history, reopen or delete trips, JSON backup/restore, 1-click PDF with emergency contacts and pre-trip checklist |

## Tech stack

- Python 3.10+
- Streamlit (UI)
- Gemini or Groq via REST (`requests`)
- pandas (cost tables), fpdf2 (PDF)
- No external database: trips live in `st.session_state`

## Run locally

```bash
git clone https://github.com/<your-username>/travel-planner.git
cd travel-planner
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push `app.py` and `requirements.txt` to a GitHub repo.
2. Go to https://share.streamlit.io, click **Create app**, and select the repo, branch `main` and file `app.py`.
3. Optional: under **Settings → Secrets**, add one of:
   ```toml
   GEMINI_API_KEY = "your-key"
   GROQ_API_KEY = "your-key"
   ```

## Using AI mode

1. Turn off **Demo mode** in the sidebar.
2. Choose a provider and paste your key. Free keys: [Gemini](https://aistudio.google.com/apikey), [Groq](https://console.groq.com/keys).
3. Leave **Model** empty to use the default, or type a model name (e.g. `llama-3.3-70b-versatile` for Groq).

Keys entered in the sidebar stay in session memory only and are never written to disk.

## Demo mode

Works with no key using a built-in library of six cities: Goa, Jaipur, Manali, Bali, Paris and Tokyo. Destinations outside this list fall back to the closest vibe match. Free-form swaps and any destination need an API key.

## Troubleshooting

| Error | Fix |
|---|---|
| 404 model error | Clear the Model box, or enter a currently available model name |
| 403 key not permitted (Gemini) | Create the key in a new project, or switch to Groq |
| 503 / network error | Provider overloaded; the app retries automatically, then wait and retry |
| 401 | Invalid API key |

## Limitations

- Trips are stored per session and reset when the app restarts. Use **Download all trips (JSON)** to keep them.
- Costs and exchange rates are indicative estimates. Verify locally before travelling.
- AI-generated plans may contain outdated details such as opening hours and prices.

## Project structure

```
app.py             # entire application (config, LLM client, engine, UI, PDF)
requirements.txt   # streamlit, requests, pandas, fpdf2
README.md
```
