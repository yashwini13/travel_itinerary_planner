"""
Personalized Travel Itinerary Planner  -  Skill Wallet Capstone Project 4
Single-file Streamlit app. No external DB: trips live in st.session_state with JSON backup/restore.
LLM: Gemini or Groq (REST via requests). Demo mode works with zero API keys.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import random
import re
import uuid
from copy import deepcopy

import pandas as pd
import requests
import streamlit as st
from fpdf import FPDF

st.set_page_config(page_title="Wanderlust Planner", page_icon="🧭", layout="wide")

# ───────────────────────────── 1. CONSTANTS ─────────────────────────────
SLOTS = [
    ("Morning Sightseeing", "09:00"),
    ("Lunch Recommendation", "13:00"),
    ("Afternoon Leisure", "15:30"),
    ("Evening Dining & Entertainment", "19:30"),
]
SLOT_ICONS = ["🌅", "🍽️", "🌴", "🌃"]
BUDGET_PER_DAY_USD = {"Budget": 70, "Moderate": 160, "Luxury": 400}  # per person
BUDGET_MULT = {"Budget": 0.6, "Moderate": 1.0, "Luxury": 2.2}
VIBES = ["Beach", "Mountains", "Cultural", "Urban"]
INTERESTS = ["Food", "Adventure", "History", "Nightlife"]
GEMINI_MODEL_DEFAULT = "gemini-flash-lite-latest"
GROQ_MODEL_DEFAULT = "llama-3.3-70b-versatile"
CHECKLIST = [
    "Passport / ID + 2 photocopies (keep separate)", "Visa / e-visa / entry permits",
    "Travel insurance policy number saved offline", "Flight & hotel confirmations downloaded",
    "Local currency + 1 backup card", "Phone charger, power bank, plug adapter",
    "Prescription medicines + basic first-aid kit", "Embassy / consulate contact saved",
    "Family contact informed of itinerary", "Offline maps downloaded",
]

# ───────────────────────── 2. DEMO KNOWLEDGE BASE ───────────────────────
# Item format: "Name|Short description|USD per person|Tag,Tag"  (tag 'veg' = vegetarian-friendly)
def _p(s: str) -> dict:
    n, d, c, t = s.split("|")
    return dict(title=n, description=d, cost_usd=float(c), tags=[x.strip() for x in t.split(",")])


def _area(c, a, l, e, n):
    return dict(c=c, a=[_p(x) for x in a], l=[_p(x) for x in l], e=[_p(x) for x in e], n=[_p(x) for x in n])


CITIES = {
    "Goa, India": dict(
        country="India", vibes=["Beach", "Nightlife"], months=[11, 12, 1, 2, 3], budget=["Budget", "Moderate"],
        tags=["Beaches", "Nightlife", "Seafood"], interests=["Food", "Adventure", "Nightlife"], cur="INR", rate=88.0,
        emerg={"Police": "112", "Ambulance": "108", "Tourist Helpline": "1363"}, blurb="Sun, sand and susegad.",
        areas={
            "North Goa": _area((15.55, 73.76),
                ["Fort Aguada & lighthouse|Sea-facing Portuguese fort|3|History,Outdoor",
                 "Parasailing at Calangute|Water sports session|25|Adventure,Outdoor",
                 "Anjuna Flea Market|Hippie market and street art|5|Market,Outdoor,Food"],
                ["Vagator cliff sunset walk|Easy cliff-top stroll and chai|2|Relax,Outdoor"],
                ["Britto's Baga|Goan seafood thali|14|Food", "Gunpowder Assagao|Southern Indian-Goan plates|12|Food,veg",
                 "Vegan cafe Nom Nom|Plant-based lunch bowls|8|Food,veg"],
                ["Tito's Lane nightlife|Beach clubs and DJ sets|30|Nightlife", "Chapora sunset shack dinner|Live music by the sea|18|Food,Nightlife,veg"]),
            "South Goa": _area((15.18, 73.98),
                ["Palolem kayaking|Calm-bay kayak at sunrise|15|Adventure,Outdoor,Nature",
                 "Cabo de Rama Fort|Quiet clifftop fort|2|History,Outdoor",
                 "Spice plantation tour|Guided farm walk with lunch|18|Nature,Food,veg"],
                ["Agonda beach lounging|Empty beach, hammocks|0|Relax,Outdoor"],
                ["Fisherman's Wharf Palolem|Catch-of-the-day grill|13|Food", "Cafe Zoca Agonda|Brunch and juices|9|Food,veg",
                 "Thalassa Greek taverna|Sunset Greek dinner|20|Food,veg"],
                ["Silent Noise Headphone Party|Open-air silent disco|20|Nightlife", "Palolem beach bonfire|Drum circle and snacks|8|Nightlife,Relax,veg"]),
        }),
    "Jaipur, India": dict(
        country="India", vibes=["Cultural"], months=[10, 11, 12, 1, 2, 3], budget=["Budget", "Moderate", "Luxury"],
        tags=["Palaces", "Bazaars", "Heritage"], interests=["History", "Food"], cur="INR", rate=88.0,
        emerg={"Police": "112", "Ambulance": "108", "Tourist Helpline": "1363"}, blurb="The Pink City of forts and flavours.",
        areas={
            "Old City": _area((26.92, 75.82),
                ["City Palace & Hawa Mahal|Royal complex and facade|10|History,Culture,Art",
                 "Jantar Mantar|UNESCO astronomical observatory|4|History,Culture",
                 "Johari Bazaar walk|Jewellery and textiles market|0|Market,Outdoor,Food"],
                ["Albert Hall Museum|Indo-Saracenic museum|3|Art,History,Relax"],
                ["Laxmi Misthan Bhandar|Rajasthani thali|7|Food,veg", "Handi Restaurant|Classic North Indian curries|9|Food",
                 "Tapri Central|Chai and snacks terrace|6|Food,veg"],
                ["Chokhi Dhani village dinner|Folk dance and thali|22|Food,Culture,Nightlife,veg", "Rooftop dinner at 1135 AD|Fort-view fine dining|40|Food,Nightlife"]),
            "Amer Side": _area((26.99, 75.85),
                ["Amer Fort|Hilltop palace with mirror hall|12|History,Culture,Outdoor",
                 "Jaigarh Fort|Cannon foundry and views|6|History,Outdoor,Adventure",
                 "Panna Meena ka Kund|Stepwell photo stop|0|History,Art,Outdoor"],
                ["Jal Mahal promenade|Lake palace stroll|0|Relax,Outdoor"],
                ["Anokhi Cafe|Organic cafe lunch|8|Food,veg", "Suvarna Mahal|Palace dining|35|Food", "Dal Baati stall Amer|Street dal baati churma|4|Food,veg"],
                ["Nahargarh sunset sundowner|Fort-top drinks|18|Nightlife,Outdoor", "Bar Palladio|Italian-Rajasthani garden dinner|30|Food,Nightlife,veg"]),
        }),
    "Manali, India": dict(
        country="India", vibes=["Mountains"], months=[3, 4, 5, 6, 9, 10], budget=["Budget", "Moderate"],
        tags=["Himalayas", "Trekking", "Cafes"], interests=["Adventure", "Food"], cur="INR", rate=88.0,
        emerg={"Police": "112", "Ambulance": "108", "Mountain Rescue (HP)": "1077"}, blurb="Himalayan valleys and adrenaline.",
        areas={
            "Old Manali & Vashisht": _area((32.26, 77.18),
                ["Hadimba Temple & cedar forest|Wooden temple in deodars|2|Culture,Nature,Outdoor",
                 "Jogini Falls trek|Easy 3 km waterfall trek|3|Adventure,Nature,Outdoor",
                 "Vashisht hot springs|Natural sulphur baths|2|Relax,Culture"],
                ["Old Manali cafe hopping|Riverside cafes|5|Relax,Food,veg"],
                ["Cafe 1947|River-view continental|10|Food,veg", "Chopsticks|Tibetan momos and thukpa|6|Food", "Johnson's Cafe|Trout and garden lunch|14|Food"],
                ["Bonfire at riverside camp|Live acoustic music|12|Nightlife,Outdoor,veg", "Lazy Dog Lounge|Mountain-view dinner|15|Food,Nightlife"]),
            "Solang & Atal Tunnel": _area((32.32, 77.15),
                ["Solang Valley paragliding|Tandem flights|35|Adventure,Outdoor",
                 "Atal Tunnel & Sissu|Engineering marvel and lake|6|Nature,Outdoor",
                 "Snow-point ATV ride|Quad bikes on snowfields|20|Adventure,Outdoor"],
                ["Sissu Lake picnic|Quiet lake time|0|Relax,Nature,Outdoor"],
                ["Dhaba at Solang|Rajma-chawal and chai|4|Food,veg", "Hotel Solang Valley restaurant|Buffet lunch|11|Food,veg",
                 "Mountain Cafe Sissu|Pasta and cocoa|8|Food,veg"],
                ["Camp dinner under the stars|Barbecue and stargazing|18|Nightlife,Outdoor,Food", "Mall Road night stroll|Shops and street food|6|Market,Food,veg"]),
        }),
    "Bali, Indonesia": dict(
        country="Indonesia", vibes=["Beach", "Cultural"], months=[4, 5, 6, 7, 8, 9, 10], budget=["Budget", "Moderate", "Luxury"],
        tags=["Temples", "Surf", "Rice Terraces"], interests=["Adventure", "Food", "History"], cur="IDR", rate=16300.0,
        emerg={"Police": "110", "Ambulance": "118 / 119", "Tourist Police Bali": "+62 361 224111"}, blurb="Temples, terraces and surf breaks.",
        areas={
            "Ubud": _area((-8.51, 115.26),
                ["Tegalalang rice terraces|Terraced paddies at sunrise|3|Nature,Outdoor",
                 "Ubud Palace & Market|Royal palace and craft market|6|Culture,Market,History",
                 "Sacred Monkey Forest|Temple and forest sanctuary|5|Nature,Culture,Outdoor"],
                ["Tirta Empul spa & holy spring|Purification ritual|8|Relax,Culture"],
                ["Naughty Nuri's|Famous grilled ribs|10|Food", "Clear Cafe|Plant-based Balinese|9|Food,veg", "Warung Biah Biah|Local small plates|6|Food,veg"],
                ["Legong dance at Ubud Palace|Traditional dance night|9|Culture,Nightlife,veg", "Locavore dinner|Tasting menu|60|Food,Nightlife"]),
            "Uluwatu & Canggu": _area((-8.82, 115.09),
                ["Uluwatu Temple|Cliff temple and Kecak dance|5|History,Culture,Outdoor",
                 "Surf lesson at Canggu|Beginner surf|25|Adventure,Outdoor",
                 "Padang Padang beach|Hidden-cove beach|2|Nature,Outdoor"],
                ["Single Fin sunset|Cliff-side drinks|10|Relax,Nightlife"],
                ["Warung Bernadette|Seafood by the sea|11|Food", "Shady Shack Canggu|Healthy bowls|9|Food,veg", "Bali Bowls Uluwatu|Smoothie bowls|7|Food,veg"],
                ["Finns Beach Club|Beach club night|25|Nightlife", "La Brisa Canggu|Boho sunset dinner|22|Food,Nightlife,veg"]),
        }),
    "Paris, France": dict(
        country="France", vibes=["Cultural", "Urban"], months=[4, 5, 6, 9, 10], budget=["Moderate", "Luxury"],
        tags=["Museums", "Cafes", "Romance"], interests=["History", "Food", "Nightlife"], cur="EUR", rate=0.92,
        emerg={"EU Emergency": "112", "Police": "17", "Ambulance (SAMU)": "15"}, blurb="Art, architecture and unhurried dining.",
        areas={
            "Left Bank & Centre": _area((48.855, 2.34),
                ["Louvre Museum|World's largest art museum|20|Art,History,Culture",
                 "Notre-Dame & Sainte-Chapelle|Gothic icons|15|History,Culture",
                 "Musee d'Orsay|Impressionist masterpieces|18|Art,History"],
                ["Luxembourg Gardens|Park stroll and boat pond|0|Relax,Outdoor"],
                ["Bouillon Chartier|Classic French brasserie|18|Food", "Le Potager du Marais|Vegetarian French|22|Food,veg", "Cafe de Flore|Iconic cafe lunch|25|Food"],
                ["Seine dinner cruise|Evening illuminated cruise|60|Food,Nightlife", "Jazz at Le Caveau de la Huchette|Live jazz cellar|15|Nightlife,Culture,veg"]),
            "Montmartre & North": _area((48.886, 2.343),
                ["Sacre-Coeur & Montmartre|Hilltop basilica and artists' square|0|Art,Culture,Outdoor",
                 "Moulin Rouge district walk|Cabaret history|0|History,Nightlife,Outdoor",
                 "Marche aux Puces|Giant flea market|0|Market,Outdoor"],
                ["Canal Saint-Martin picnic|Canal-side relax|10|Relax,Outdoor,Food,veg"],
                ["Le Consulat|Old-style Montmartre bistro|20|Food", "Hardware Societe|Brunch spot|16|Food,veg", "Le Grenier a Pain|Boulangerie lunch|9|Food,veg"],
                ["Moulin Rouge show|Iconic cabaret|110|Nightlife,Culture", "Le Mary Celeste|Cocktails and small plates|35|Nightlife,Food,veg"]),
        }),
    "Tokyo, Japan": dict(
        country="Japan", vibes=["Urban", "Cultural"], months=[3, 4, 5, 10, 11], budget=["Moderate", "Luxury"],
        tags=["Neon", "Ramen", "Temples"], interests=["Food", "Nightlife", "History", "Adventure"], cur="JPY", rate=152.0,
        emerg={"Police": "110", "Ambulance/Fire": "119", "Japan Visitor Hotline": "050-3816-2787"}, blurb="Neon skylines and quiet shrines.",
        areas={
            "Asakusa & Ueno": _area((35.71, 139.79),
                ["Senso-ji Temple|Tokyo's oldest temple|0|History,Culture,Outdoor",
                 "Ueno Park & Tokyo National Museum|Art and heritage|9|History,Art,Culture",
                 "Ameyoko Market|Street food alley|5|Market,Food,Outdoor"],
                ["Sumida River cruise|Scenic water bus|8|Relax,Outdoor"],
                ["Asakusa Ramen Ichiran|Tonkotsu ramen|9|Food", "Daikokuya Tempura|Century-old tempura|14|Food", "Shojin Ryori Daigo|Buddhist vegetarian|25|Food,veg"],
                ["Hoppy Street izakaya|Yakitori and highballs|20|Food,Nightlife", "Asakusa Kagura rooftop|Skytree-view dinner|35|Food,Nightlife,veg"]),
            "Shibuya & Shinjuku": _area((35.68, 139.7),
                ["Meiji Shrine|Forest shrine|0|History,Culture,Nature",
                 "Shibuya Sky|Rooftop city views|15|Outdoor,Urban",
                 "Harajuku Takeshita Street|Youth fashion lane|0|Market,Outdoor"],
                ["Shinjuku Gyoen garden|Landscaped park|4|Relax,Nature,Outdoor"],
                ["Afuri Ramen|Yuzu shio ramen|10|Food", "T's Tantan Tokyo Station|Vegan ramen|9|Food,veg", "Omoide Yokocho|Alley yakitori|15|Food"],
                ["Golden Gai bar crawl|Tiny themed bars|25|Nightlife", "Robot Restaurant-style show Kabukicho|Neon entertainment|45|Nightlife,Culture,veg"]),
        }),
}

# ───────────────────────────── 3. UTILITIES ─────────────────────────────
def haversine(a, b) -> float:
    r = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def day_km(day: dict) -> float | None:
    pts = [(s["lat"], s["lng"]) for s in day["slots"] if s.get("lat") is not None and s.get("lng") is not None]
    if len(pts) < 2:
        return None
    return round(sum(haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1)), 1)


def season_of(month: int) -> str:
    return {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
            6: "Summer", 7: "Summer", 8: "Summer"}.get(month, "Autumn")


def fmt_money(v: float, code: str = "") -> str:
    s = f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.2f}"
    return f"{code} {s}".strip()


def extract_json(text: str) -> dict:
    text = re.sub(r"```(?:json)?", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model did not return JSON.")
    return json.loads(text[start:end + 1])


def pdf_safe(t) -> str:
    t = str(t)
    for k, v in {"₹": "INR ", "€": "EUR ", "£": "GBP ", "¥": "JPY ", "–": "-", "—": "-", "’": "'",
                 "‘": "'", "“": '"', "”": '"', "•": "-", "…": "...", "→": "->"}.items():
        t = t.replace(k, v)
    return t.encode("latin-1", "ignore").decode("latin-1")


# ───────────────────────────── 4. LLM CLIENT ─────────────────────────────
SYSTEM_PROMPT = ("You are a senior travel planner. Reply with ONE valid JSON object only: no markdown, "
                 "no commentary. Use realistic, real places and prices.")


import time

def _post(url, **kw):
    """POST with automatic retry on temporary server errors."""
    for i in range(3):
        try:
            r = requests.post(url, **kw)
        except requests.RequestException:
            if i == 2:
                raise
            time.sleep(2 * (i + 1))
            continue
        if r.status_code not in (429, 500, 502, 503, 504):
            return r
        time.sleep(2 * (i + 1))
    return r

def call_llm(provider: str, key: str, model: str, prompt: str, temperature: float = 0.7) -> dict:
    """Calls Gemini or Groq over REST. API key is sent in headers only (never logged or put in URLs)."""
    try:
        if provider == "Gemini":
            r = _post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json={"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                      "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"}},
                timeout=90)
            r.raise_for_status()
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        else:
            r = _post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "temperature": temperature, "response_format": {"type": "json_object"},
                      "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]},
                timeout=90)
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        return extract_json(text)
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        hint = {400: "bad request / invalid model name", 401: "invalid API key", 403: "key not permitted",
                429: "rate limit hit, retry shortly"}.get(code, "provider error")
        try:
            detail = e.response.json().get("error", {})
            detail = detail.get("message", "") if isinstance(detail, dict) else str(detail)
        except Exception:
            detail = ""
        raise RuntimeError(f"{provider} API error {code}: {hint}. {detail}") from None
    except requests.RequestException:
        raise RuntimeError(f"Network error while contacting {provider}.") from None
    except (KeyError, IndexError, ValueError):
        raise RuntimeError("The model returned an unreadable response. Try again.") from None


def llm_ready() -> bool:
    return (not st.session_state.demo_mode) and bool(st.session_state.api_key)


def ask_llm(prompt: str, temperature: float = 0.7) -> dict:
    default = GEMINI_MODEL_DEFAULT if st.session_state.provider == "Gemini" else GROQ_MODEL_DEFAULT
    model = (st.session_state.model or "").strip().strip("\"'") or default
    key = st.session_state.api_key.strip().strip("\"'")
    return call_llm(st.session_state.provider, key, model, prompt, temperature)


# ───────────────────────── 5. RECOMMENDER (Tab 1) ─────────────────────────
def prefs_brief(p: dict) -> str:
    return (f"Budget: {p['budget']}; party: {p['party']} ({p['travelers']} travelers); pace: {p['pace']}; "
            f"interests: {', '.join(p['interests']) or 'general'}; vegetarian: {p['vegetarian']}; "
            f"start date: {p['start']}; days: {p['days']}")


def demo_recommend(p: dict) -> list[dict]:
    month = dt.date.fromisoformat(p["start"]).month
    out = []
    for name, c in CITIES.items():
        score = 0
        score += 40 if p["vibe"] in c["vibes"] else 0
        score += 25 if p["budget"] in c["budget"] else 0
        score += 20 if month in c["months"] else 0
        score += 5 * len(set(p["interests"]) & set(c["interests"]))
        out.append(dict(
            city=name, country=c["country"], match_score=min(score, 100), highlights=c["tags"], blurb=c["blurb"],
            season_note=("In season" if month in c["months"] else "Off-peak: expect weather trade-offs") + f" ({season_of(month)})",
            est_daily_budget_usd=round(BUDGET_PER_DAY_USD[p["budget"]] * (0.6 if "India" in name else 1.0)),
            why=f"Matches your {p['vibe']} mood" + (f", fits a {p['budget']} budget" if p["budget"] in c["budget"] else "") + "."))
    return sorted(out, key=lambda x: -x["match_score"])[:3]


def get_recommendations(p: dict) -> list[dict]:
    if not llm_ready():
        return demo_recommend(p)
    prompt = (f"Recommend the top 3 cities for a trip. Mood/vibe: {p['vibe']}. {prefs_brief(p)}. "
              "Consider weather for the travel month. JSON: {\"recommendations\":[{\"city\":\"City, Country\","
              "\"country\":\"\",\"match_score\":0-100,\"highlights\":[\"3-4 short tags\"],\"blurb\":\"one line\","
              "\"season_note\":\"weather in that month\",\"est_daily_budget_usd\":number,\"why\":\"one sentence\"}]}")
    return ask_llm(prompt)["recommendations"][:3]


# ───────────────────── 6. ITINERARY ENGINE (Tab 2 & 3) ─────────────────────
def _coords(center, title):
    r = random.Random(title)
    return round(center[0] + (r.random() - .5) * 0.03, 5), round(center[1] + (r.random() - .5) * 0.03, 5)


def _slot(idx, item, area, center, p, note=""):
    lat, lng = _coords(center, item["title"])
    return dict(slot=SLOTS[idx][0], time=SLOTS[idx][1], title=item["title"], description=item["description"] + (f" {note}" if note else ""),
                area=area, cost_usd=round(item["cost_usd"] * BUDGET_MULT[p["budget"]], 1), lat=lat, lng=lng, tags=item["tags"])


def _pick(pool, used, rng, want=(), veg=False, cheap=False, avoid=()):
    c = [x for x in pool if x["title"] not in used] or [x for x in pool if x["title"] not in avoid] or pool
    if veg and any("veg" in x["tags"] for x in c):
        c = [x for x in c if "veg" in x["tags"]]
    if cheap:
        return sorted(c, key=lambda x: x["cost_usd"])[0]
    return max(c, key=lambda x: sum(2 for w in want if w in x["tags"]) + rng.random())


def resolve_demo_city(dest: str, vibe: str) -> tuple[str, bool]:
    d = (dest or "").lower()
    for k in CITIES:
        if d and (d in k.lower() or k.split(",")[0].lower() in d):
            return k, True
    best = next((k for k, c in CITIES.items() if vibe in c["vibes"]), next(iter(CITIES)))
    return best, False


def demo_day(city_key, p, day_no, area, rng, used, want=()):
    c = CITIES[city_key]
    a = c["areas"][area]
    want = list(want) + p["interests"]
    veg = p["vegetarian"]
    leisure_pool = {"Relaxed": a["l"], "Fast-Paced": a["a"]}.get(p["pace"], a["l"] + a["a"])
    picks, today = [], set()
    for pool, v in ((a["a"], False), (a["e"], veg), (leisure_pool, False), (a["n"], veg)):
        item = _pick(pool, used, rng, want, veg=v, avoid=today)
        used.add(item["title"])
        today.add(item["title"])  # update immediately so a day never repeats a place
        picks.append(item)
    return dict(day=day_no, theme=f"{area} day", area=area,
                slots=[_slot(i, it, area, a["c"], p) for i, it in enumerate(picks)])


def demo_itinerary(p: dict, seed: int = 7) -> dict:
    key, exact = resolve_demo_city(p["destination"], p["vibe"])
    c = CITIES[key]
    areas, rng, used, days = list(c["areas"]), random.Random(seed), set(), []
    for i in range(p["days"]):
        area = areas[min(i * len(areas) // p["days"], len(areas) - 1)]  # contiguous blocks = no backtracking
        days.append(demo_day(key, p, i + 1, area, rng, used))
    return dict(destination=key, currency=c["cur"], usd_to_local=c["rate"], emergency=c["emerg"], days=days, demo_key=key,
                notice=None if exact else f"'{p['destination'] or 'your vibe'}' isn't in the demo library, so {key} is used. Add an API key for any destination.")


def normalize(it: dict, p: dict) -> dict:
    it.setdefault("destination", p["destination"])
    it["currency"] = str(it.get("currency") or "USD")
    it["usd_to_local"] = float(it.get("usd_to_local") or 1)
    it["emergency"] = it.get("emergency") or {"General Emergency": "112"}
    for i, d in enumerate(it["days"]):
        d["day"] = i + 1
        d.setdefault("theme", f"Day {i + 1}")
        d.setdefault("area", "")
        fixed = []
        for j, (name, t) in enumerate(SLOTS):
            s = next((x for x in d["slots"] if x.get("slot") == name), d["slots"][j] if j < len(d["slots"]) else {})
            fixed.append(dict(slot=name, time=s.get("time", t), title=s.get("title", "Free time"), description=s.get("description", ""),
                              area=s.get("area", d["area"]), cost_usd=float(s.get("cost_usd") or 0),
                              lat=_num(s.get("lat")), lng=_num(s.get("lng")), tags=s.get("tags", [])))
        d["slots"] = fixed
    return it


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


SLOT_SCHEMA = ('{"slot":"<exact slot name>","time":"HH:MM","title":"","description":"1-2 sentences","area":"neighbourhood",'
               '"cost_usd":number per person,"lat":number,"lng":number}')


def generate_itinerary(p: dict) -> dict:
    if not llm_ready():
        return demo_itinerary(p)
    prompt = (
        f"Create a {p['days']}-day itinerary for {p['destination']}. {prefs_brief(p)}.\n"
        "RULES: (1) GEOGRAPHIC CLUSTERING: each day focuses on ONE neighbourhood/area; group nearby attractions; order days so "
        "areas progress without backtracking; never span multiple cities. (2) Exactly 4 slots per day, in this order with these exact names: "
        + ", ".join(n for n, _ in SLOTS) + ". (3) cost_usd is per person in USD, realistic for the budget level. (4) Provide lat/lng for each "
        "slot. (5) Respect pace, interests and vegetarian needs. (6) Give local currency ISO code, usd_to_local (units of local currency per 1 USD) "
        "and emergency numbers for the country.\n"
        f"JSON: {{\"destination\":\"\",\"currency\":\"ISO\",\"usd_to_local\":number,\"emergency\":{{\"Police\":\"\",\"Ambulance\":\"\",\"Tourist helpline\":\"\"}},"
        f"\"days\":[{{\"theme\":\"\",\"area\":\"\",\"slots\":[{SLOT_SCHEMA}]}}]}}")
    return normalize(ask_llm(prompt, 0.6), p)


def day_context(it, skip_day):
    return [s["title"] for d in it["days"] if d["day"] != skip_day for s in d["slots"]]


def regen_day(it: dict, di: int, p: dict, style: str, custom: str) -> dict:
    day = it["days"][di]
    if it.get("demo_key") and not llm_ready():
        c = CITIES[it["demo_key"]]
        want = {"Foodie focus": ["Food"], "Adventure": ["Adventure", "Outdoor"], "Relaxed": ["Relax"], "Culture & history": ["History", "Culture", "Art"],
                "Nightlife": ["Nightlife"], "Off-beat / local": ["Market", "Local"]}.get(style, [])
        rng = random.Random(random.randint(0, 10 ** 6))
        return demo_day(it["demo_key"], p, day["day"], day["area"], rng, set(day_context(it, day["day"])), want)
    prompt = (f"Rewrite ONLY day {day['day']} of a trip to {it['destination']}. {prefs_brief(p)}.\nCurrent day: {json.dumps(day)}\n"
              f"Vibe change: {style}. Extra instruction: {custom or 'none'}.\nKeep the same neighbourhood ({day['area']}) unless impossible; avoid repeating these "
              f"places: {day_context(it, day['day'])[:30]}. Keep the 4 exact slot names. JSON: {{\"theme\":\"\",\"area\":\"\",\"slots\":[{SLOT_SCHEMA}]}}")
    new = ask_llm(prompt, 0.8)
    tmp = normalize(dict(destination=it["destination"], days=[new]), p)["days"][0]
    tmp["day"] = day["day"]
    return tmp


KEYWORDS = {"market": ["Market"], "outdoor": ["Outdoor", "Nature"], "park": ["Outdoor", "Nature"], "vegetarian": ["veg"], "veg": ["veg"],
            "museum": ["Art", "History", "Culture"], "history": ["History"], "adventure": ["Adventure"], "night": ["Nightlife"],
            "bar": ["Nightlife"], "relax": ["Relax"], "spa": ["Relax"], "food": ["Food"], "culture": ["Culture"], "nature": ["Nature"]}


def swap_slot(it: dict, di: int, si: int, p: dict, instruction: str) -> dict:
    day, old = it["days"][di], it["days"][di]["slots"][si]
    if it.get("demo_key") and not llm_ready():
        a = CITIES[it["demo_key"]]["areas"][day["area"]]
        pool = [[*a["a"], *a["l"]], a["e"], [*a["l"], *a["a"]], [*a["n"], *a["e"]]][si]
        ins = instruction.lower()
        want = sorted({t for k, v in KEYWORDS.items() if k in ins for t in v})
        used = {s["title"] for d in it["days"] for s in d["slots"]}
        cands = [x for x in pool if x["title"] not in used] or [x for x in pool if x["title"] != old["title"]]
        matched = [x for x in cands if set(want) & set(x["tags"])] if want else cands
        note = "" if matched or not want else "(No exact demo match; closest alternative chosen. Add an API key for free-form swaps.)"
        item = _pick(matched or cands, used, random.Random(), want, veg="veg" in want,
                     cheap=any(w in ins for w in ("cheap", "budget", "afford")))
        return _slot(si, item, day["area"], a["c"], p, note)
    prompt = (f"Replace ONE activity in day {day['day']} ({day['area']}) of a trip to {it['destination']}. {prefs_brief(p)}.\nDay: {json.dumps(day)}\n"
              f"Slot to replace: '{old['slot']}' ({old['title']}). User request: {instruction}.\nStay in the same area so transit stays short; do not repeat: "
              f"{day_context(it, -1)[:30]}. JSON: {SLOT_SCHEMA}")
    s = ask_llm(prompt, 0.8)
    s["slot"] = old["slot"]
    s.setdefault("area", day["area"])
    return normalize(dict(days=[dict(slots=[s] * 4)]), p)["days"][0]["slots"][0] | {"slot": old["slot"], "time": old["time"]}


# ───────────────────────────── 7. ANALYTICS ─────────────────────────────
def itinerary_df(it: dict, travelers: int, usd_inr: float) -> pd.DataFrame:
    rows, cum = [], 0.0
    for d in it["days"]:
        for s in d["slots"]:
            usd = s["cost_usd"] * travelers
            cum += usd
            rows.append({"Day": d["day"], "Time": s["time"], "Slot": s["slot"], "Activity": s["title"], "Area": s["area"],
                         f"Cost ({it['currency']})": round(usd * it["usd_to_local"]), "Cost (USD)": round(usd, 2),
                         "Cost (INR)": round(usd * usd_inr), "Cumulative (USD)": round(cum, 2)})
    return pd.DataFrame(rows)


# ───────────────────────── 8. PERSISTENCE (simulated DB) ─────────────────────────
def save_trip(name: str, p: dict, it: dict) -> str:
    tid = uuid.uuid4().hex[:8]
    st.session_state.trips[tid] = dict(id=tid, name=name.strip() or it["destination"], saved_at=dt.datetime.now().isoformat(timespec="minutes"),
                                       prefs=deepcopy(p), itinerary=deepcopy(it))
    return tid


def import_backup(raw: bytes) -> int:
    data = json.loads(raw.decode("utf-8"))
    n = 0
    for t in data.get("trips", []):
        if {"id", "name", "prefs", "itinerary"} <= t.keys():
            st.session_state.trips[t["id"]] = t
            n += 1
    return n


# ───────────────────────────── 9. PDF EXPORT ─────────────────────────────
class TravelPDF(FPDF):
    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 6, "Personalized Travel Itinerary - offline guide", new_x="LMARGIN", new_y="NEXT", align="R")

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")

    def h(self, txt, size=14, color=(14, 116, 144)):
        self.set_font("Helvetica", "B", size)
        self.set_text_color(*color)
        self.cell(0, 9, pdf_safe(txt), new_x="LMARGIN", new_y="NEXT")

    def para(self, txt, size=10, bold=False, color=(40, 40, 40), indent=0):
        self.set_font("Helvetica", "B" if bold else "", size)
        self.set_text_color(*color)
        self.set_x(self.l_margin + indent)
        self.multi_cell(0, 5.5, pdf_safe(txt), new_x="LMARGIN", new_y="NEXT")


def build_pdf(trip: dict, usd_inr: float) -> bytes:
    p, it = trip["prefs"], trip["itinerary"]
    trav = p["travelers"]
    pdf = TravelPDF(format="A4")
    pdf.set_auto_page_break(True, 16)
    pdf.add_page()
    pdf.set_fill_color(14, 116, 144)
    pdf.rect(0, 0, 210, 58, "F")
    pdf.set_y(16)
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 12, pdf_safe(it["destination"]), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, f"{p['days']}-Day Itinerary  |  {p['start']}  |  {p['party']} ({trav} traveler{'s' if trav > 1 else ''})", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(0, 8, f"{p['budget']} budget  |  {p['pace']} pace  |  Interests: {', '.join(p['interests']) or 'General'}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_y(66)

    df = itinerary_df(it, trav, usd_inr)
    total = df["Cost (USD)"].sum()
    pdf.h("Trip budget summary")
    pdf.para(f"Estimated total: USD {total:,.0f}  |  {it['currency']} {total * it['usd_to_local']:,.0f}  |  INR {total * usd_inr:,.0f}", bold=True)
    pdf.para(f"Indicative rates: 1 USD = {it['usd_to_local']:,.2f} {it['currency']} = {usd_inr:,.2f} INR. Estimates only; verify locally.", 9, color=(110, 110, 110))
    pdf.ln(3)

    for d in it["days"]:
        km = day_km(d)
        day_total = sum(s["cost_usd"] for s in d["slots"]) * trav
        if pdf.get_y() > 235:
            pdf.add_page()
        pdf.set_fill_color(224, 242, 247)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(8, 80, 100)
        pdf.cell(0, 9, pdf_safe(f" Day {d['day']}: {d['theme']}  ({d['area']})"), new_x="LMARGIN", new_y="NEXT", fill=True)
        for s in d["slots"]:
            if pdf.get_y() > 255:
                pdf.add_page()
            pdf.para(f"{s['time']}  {s['slot']}  -  USD {s['cost_usd'] * trav:,.0f} / {it['currency']} {s['cost_usd'] * trav * it['usd_to_local']:,.0f}", 10, True, (30, 30, 30))
            pdf.para(f"{s['title']}: {s['description']}", 10, indent=6)
        pdf.para(f"Day total: USD {day_total:,.0f}" + (f"  |  approx. transit distance: {km} km" if km is not None else ""), 9, True, (14, 116, 144))
        pdf.ln(3)

    pdf.add_page()
    pdf.h("Emergency contacts")
    for k, v in it["emergency"].items():
        pdf.para(f"[ ]  {k}: {v}", 11)
    pdf.para("[ ]  Your embassy / consulate: ______________________", 11)
    pdf.para("[ ]  Hotel front desk: ______________________", 11)
    pdf.para("[ ]  Travel insurance 24h line: ______________________", 11)
    pdf.ln(4)
    pdf.h("Pre-trip checklist")
    for c in CHECKLIST:
        pdf.para(f"[ ]  {c}", 11)
    return bytes(pdf.output())


# ───────────────────────────── 10. STYLING ─────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Poppins', sans-serif; }
.hero { background: linear-gradient(120deg,#0e7490 0%,#06b6d4 45%,#f59e0b 100%); padding: 28px 32px; border-radius: 20px; color:#fff; margin-bottom: 18px; }
.hero h1 { margin:0; font-size: 2rem; } .hero p { margin:4px 0 0; opacity:.92; }
.card { background: var(--secondary-background-color); border-radius: 16px; padding: 18px; border-top: 5px solid #06b6d4; height:100%; }
.card h3 { margin: 0 0 4px; }
.tag { display:inline-block; background:#fef3c7; color:#92400e; padding:2px 10px; border-radius:999px; font-size:.75rem; margin:2px 4px 2px 0; font-weight:600; }
.slot { background: var(--secondary-background-color); border-left: 6px solid #f59e0b; border-radius: 12px; padding: 12px 16px; margin: 8px 0; }
.slot b { color:#0e7490; } .cost { float:right; font-weight:600; color:#b45309; }
.badge { background:#d1fae5; color:#065f46; padding:2px 10px; border-radius:999px; font-size:.75rem; font-weight:600; }
.badge.warn { background:#fee2e2; color:#991b1b; }
</style>
"""


# ───────────────────────────── 11. UI ─────────────────────────────
def init_state():
    defaults = dict(api_key="", provider="Gemini", model="", demo_mode=True, trips={}, recs=None, itinerary=None,
                    dest_mode="I know my destination", dest_text="", pdf_bytes=None, pdf_for=None)
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
    for prov, secret in (("Gemini", "GEMINI_API_KEY"), ("Groq", "GROQ_API_KEY")):  # optional Streamlit secrets
        try:
            if not st.session_state.api_key and secret in st.secrets:
                st.session_state.api_key, st.session_state.provider, st.session_state.demo_mode = st.secrets[secret], prov, False
        except Exception:
            pass


def choose_dest(city: str):
    st.session_state.dest_mode = "I know my destination"
    st.session_state.dest_text = city


def sidebar() -> dict:
    sb = st.sidebar
    sb.header("🔐 Configuration")
    sb.toggle("Demo mode (no API key)", key="demo_mode", help="Built-in destination library. Turn off to use Gemini/Groq.")
    if not st.session_state.demo_mode:
        sb.radio("Provider", ["Gemini", "Groq"], key="provider", horizontal=True)
        sb.text_input("API key", key="api_key", type="password", help="Kept in this session's memory only.")
        sb.text_input("Model (optional)", key="model", placeholder=GEMINI_MODEL_DEFAULT if st.session_state.provider == "Gemini" else GROQ_MODEL_DEFAULT)
        if not st.session_state.api_key:
            sb.warning("No key yet: running in demo mode.")
    sb.caption("🟢 AI mode" if llm_ready() else "🟡 Demo mode")
    sb.divider()
    sb.header("🧳 Trip preferences")
    sb.radio("How do you want to start?", ["I know my destination", "Inspire me (pick a vibe)"], key="dest_mode")
    known = st.session_state.dest_mode.startswith("I know")
    if known:
        sb.text_input("Destination", key="dest_text", placeholder="e.g. Jaipur, India")
    vibe = sb.selectbox("Travel vibe", VIBES, disabled=known and bool(st.session_state.dest_text))
    days = sb.slider("Trip duration (days)", 1, 10, 4)
    start = sb.date_input("Start date", dt.date.today() + dt.timedelta(days=30))
    sb.caption(f"Trip: {start:%d %b} → {start + dt.timedelta(days=days - 1):%d %b %Y}")
    budget = sb.select_slider("Budget level", ["Budget", "Moderate", "Luxury"], value="Moderate")
    party = sb.selectbox("Travel party", ["Solo", "Couple", "Family", "Friends"], index=1)
    travelers = sb.number_input("Number of travelers", 1, 20, {"Solo": 1, "Couple": 2}.get(party, 4))
    pace = sb.select_slider("Pace", ["Relaxed", "Moderate", "Fast-Paced"], value="Moderate")
    interests = sb.multiselect("Interests", INTERESTS, default=["Food"])
    veg = sb.checkbox("Vegetarian food only")
    usd_inr = sb.number_input("USD → INR rate", 50.0, 150.0, 88.0, step=0.5, help="Editable, indicative rate.")
    return dict(destination=(st.session_state.dest_text.strip() if known else ""), vibe=vibe, days=days, start=start.isoformat(),
                budget=budget, party=party, travelers=int(travelers), pace=pace, interests=interests, vegetarian=veg, usd_inr=float(usd_inr))


def tab_recommend(p):
    st.subheader("🗺️ Smart Destination Recommender")
    st.caption(f"Based on vibe **{p['vibe']}**, **{p['budget']}** budget, {season_of(dt.date.fromisoformat(p['start']).month)} season and your interests.")
    if st.button("✨ Recommend top 3 cities", type="primary"):
        with st.spinner("Matching destinations..."):
            try:
                st.session_state.recs = get_recommendations(p)
            except Exception as e:
                st.error(str(e))
                st.session_state.recs = demo_recommend(p)
                st.info("Showing demo recommendations instead.")
    recs = st.session_state.recs
    if recs:
        for col, (i, r) in zip(st.columns(len(recs)), enumerate(recs)):
            with col:
                tags = "".join(f"<span class='tag'>{t}</span>" for t in r.get("highlights", []))
                st.markdown(f"<div class='card'><h3>#{i + 1} {r['city']}</h3><span class='badge'>{r.get('match_score', '-')}% match</span><br>"
                            f"<p>{r.get('blurb', '')}</p>{tags}<p style='margin-top:8px'>🌤️ {r.get('season_note', '')}<br>"
                            f"💰 ~${r.get('est_daily_budget_usd', '-')}/day per person<br><i>{r.get('why', '')}</i></p></div>", unsafe_allow_html=True)
                st.button("Plan this trip →", key=f"pick{i}", on_click=choose_dest, args=(r["city"],), use_container_width=True)
        st.info("After choosing a city, open the **Itinerary** tab and click Generate.")


def render_day(it, d, p):
    km = day_km(d)
    trav, total = p["travelers"], sum(s["cost_usd"] for s in d["slots"]) * p["travelers"]
    badge = ""
    if km is not None:
        badge = f"<span class='badge{' warn' if km > 25 else ''}'>{'Compact route' if km <= 25 else 'Long transit'} · ~{km} km</span>"
    st.markdown(f"**Day {d['day']} · {d['theme']}** &nbsp; 📍 {d['area']} &nbsp; {badge} &nbsp; 💵 ${total:,.0f} / {it['currency']} {total * it['usd_to_local']:,.0f} / ₹{total * p['usd_inr']:,.0f}",
                unsafe_allow_html=True)
    for i, s in enumerate(d["slots"]):
        c = s["cost_usd"] * trav
        st.markdown(f"<div class='slot'><span class='cost'>${c:,.0f} · {it['currency']} {c * it['usd_to_local']:,.0f} · ₹{c * p['usd_inr']:,.0f}</span>"
                    f"{SLOT_ICONS[i]} <b>{s['time']} · {s['slot']}</b><br><b>{s['title']}</b><br><small>{s['description']}</small></div>", unsafe_allow_html=True)


def tab_itinerary(p):
    st.subheader("📅 Day-by-Day Optimized Itinerary")
    if st.button("🚀 Generate itinerary", type="primary"):
        if st.session_state.dest_mode.startswith("I know") and not p["destination"] and llm_ready():
            st.warning("Enter a destination in the sidebar, or use Tab 1 to pick one.")
        else:
            with st.spinner("Clustering attractions and building your plan..."):
                try:
                    pp = dict(p, destination=p["destination"] or (get_recommendations(p)[0]["city"] if llm_ready() else ""))
                    st.session_state.itinerary = generate_itinerary(pp)
                    st.session_state.plan_prefs = pp
                except Exception as e:
                    st.error(f"{e}")
    it = st.session_state.itinerary
    if not it:
        st.info("Set your preferences in the sidebar, then click **Generate itinerary**.")
        return
    pp = st.session_state.plan_prefs
    if it.get("notice"):
        st.warning(it["notice"])
    df = itinerary_df(it, pp["travelers"], pp["usd_inr"])
    total = df["Cost (USD)"].sum()
    cap = BUDGET_PER_DAY_USD[pp["budget"]] * pp["days"] * pp["travelers"]
    m = st.columns(4)
    m[0].metric("Destination", it["destination"])
    m[1].metric("Total (USD)", f"${total:,.0f}")
    m[2].metric(f"Total ({it['currency']})", fmt_money(total * it["usd_to_local"]))
    m[3].metric("Total (INR)", f"₹{total * pp['usd_inr']:,.0f}")
    st.progress(min(total / cap, 1.0), text=f"{total / cap:.0%} of {pp['budget']} guideline budget (${cap:,.0f})")
    if total > cap:
        st.error("Over the guideline budget. Use the Vibe Customization tab to swap costly activities.")
    for d in it["days"]:
        with st.expander(f"Day {d['day']} · {d['theme']}", expanded=d["day"] == 1):
            render_day(it, d, pp)
    st.markdown("#### 📈 Running budget tracker")
    st.line_chart(df.set_index(df.index + 1)["Cumulative (USD)"], height=220)
    st.dataframe(df, hide_index=True, use_container_width=True)
    st.download_button("⬇️ Download cost table (CSV)", df.to_csv(index=False).encode(), "itinerary_costs.csv", "text/csv")


def tab_customize(p):
    st.subheader("🎨 Vibe Customization & Dynamic Swap")
    it = st.session_state.itinerary
    if not it:
        st.info("Generate an itinerary first.")
        return
    pp = st.session_state.plan_prefs
    c1, c2 = st.columns(2)
    day_no = c1.selectbox("Day", [d["day"] for d in it["days"]], format_func=lambda x: f"Day {x}: {it['days'][x - 1]['theme']}")
    di = day_no - 1
    si = c2.selectbox("Slot", range(4), format_func=lambda i: f"{SLOT_ICONS[i]} {SLOTS[i][0]}")
    cur = it["days"][di]["slots"][si]
    st.markdown(f"<div class='slot'>Current: <b>{cur['title']}</b><br><small>{cur['description']}</small></div>", unsafe_allow_html=True)

    presets = ["(type your own)", "Swap museum for outdoor market", "Find vegetarian lunch spot", "Something cheaper", "More adventurous",
               "More relaxing", "More nightlife", "More local food"]
    pre = st.selectbox("Quick request", presets)
    custom = st.text_input("Or describe the change", placeholder="e.g. Swap the museum for a local outdoor market")
    instr = custom or (pre if pre != presets[0] else "")
    if st.button("🔄 Swap this activity", disabled=not instr):
        with st.spinner("Finding a better fit..."):
            try:
                it["days"][di]["slots"][si] = swap_slot(it, di, si, pp, instr)
                st.success("Slot updated. Other days are untouched.")
                st.rerun()
            except Exception as e:
                st.error(str(e))
    st.divider()
    st.markdown("**Regenerate this whole day** (other days stay the same)")
    style = st.selectbox("Day vibe", ["Same area, fresh picks", "Foodie focus", "Adventure", "Relaxed", "Culture & history", "Nightlife", "Off-beat / local"])
    extra = st.text_input("Extra instruction (optional)", key="day_extra")
    if st.button("♻️ Regenerate Day " + str(day_no)):
        with st.spinner("Rebuilding the day..."):
            try:
                it["days"][di] = regen_day(it, di, pp, style, extra)
                st.rerun()
            except Exception as e:
                st.error(str(e))
    st.markdown("**Preview**")
    render_day(it, it["days"][di], pp)


def tab_manage(p):
    st.subheader("💾 Trip Management & Offline PDF")
    it = st.session_state.itinerary
    if it:
        pp = st.session_state.plan_prefs
        c1, c2 = st.columns([3, 1])
        name = c1.text_input("Trip name", value=f"{it['destination']} · {pp['days']} days", label_visibility="collapsed")
        if c2.button("💾 Save trip", use_container_width=True):
            save_trip(name, pp, it)
            st.success("Trip saved.")
    else:
        st.info("Generate an itinerary to save or export it.")

    trips = sorted(st.session_state.trips.values(), key=lambda t: t["saved_at"], reverse=True)
    st.markdown(f"#### 🗂️ Trip history ({len(trips)})")
    if not trips:
        st.caption("No saved trips yet.")
    for t in trips:
        cols = st.columns([4, 1, 1, 1])
        cols[0].markdown(f"**{t['name']}** \n<small>{t['saved_at']} · {t['prefs']['budget']} · {t['prefs']['party']}</small>", unsafe_allow_html=True)
        if cols[1].button("Open", key=f"o{t['id']}"):
            st.session_state.itinerary, st.session_state.plan_prefs = deepcopy(t["itinerary"]), deepcopy(t["prefs"])
            st.rerun()
        if cols[2].button("PDF", key=f"p{t['id']}"):
            try:
                st.session_state.pdf_bytes, st.session_state.pdf_for = build_pdf(t, t["prefs"]["usd_inr"]), t["name"]
            except Exception as e:
                st.error(f"PDF failed: {e}")
        if cols[3].button("🗑️", key=f"d{t['id']}"):
            del st.session_state.trips[t["id"]]
            st.rerun()

    st.markdown("#### 📄 1-click offline PDF guide")
    if it and st.button("📘 Build PDF for current itinerary", type="primary"):
        try:
            st.session_state.pdf_bytes = build_pdf(dict(prefs=st.session_state.plan_prefs, itinerary=it), st.session_state.plan_prefs["usd_inr"])
            st.session_state.pdf_for = it["destination"]
        except Exception as e:
            st.error(f"PDF failed: {e}")
    if st.session_state.pdf_bytes:
        fn = re.sub(r"[^A-Za-z0-9]+", "_", st.session_state.pdf_for or "trip") + "_itinerary.pdf"
        st.download_button(f"⬇️ Download {fn}", st.session_state.pdf_bytes, fn, "application/pdf")

    st.markdown("#### 🔁 Backup / restore")
    st.caption("Session storage resets when the app restarts. Download a backup to keep trips permanently.")
    b1, b2 = st.columns(2)
    b1.download_button("Download all trips (JSON)", json.dumps({"trips": trips}, indent=2).encode(), "trips_backup.json", "application/json", disabled=not trips)
    up = b2.file_uploader("Restore backup", type="json", label_visibility="collapsed")
    if up is not None and st.button("Import backup"):
        try:
            st.success(f"Imported {import_backup(up.read())} trip(s).")
            st.rerun()
        except Exception:
            st.error("Invalid backup file.")


def main():
    init_state()
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown("<div class='hero'><h1>🧭 Personalized Travel Itinerary Planner</h1>"
                "<p>Smart recommendations · clustered day plans · live budget · offline PDF</p></div>", unsafe_allow_html=True)
    p = sidebar()
    t1, t2, t3, t4 = st.tabs(["🗺️ Recommender", "📅 Itinerary", "🎨 Customize", "💾 Trips & PDF"])
    for tab, fn in ((t1, tab_recommend), (t2, tab_itinerary), (t3, tab_customize), (t4, tab_manage)):
        with tab:
            try:
                fn(p)
            except Exception as e:  # last-resort guard so one tab never crashes the app
                st.error(f"Something went wrong: {e}")


main()