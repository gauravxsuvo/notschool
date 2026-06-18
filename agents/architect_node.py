import json
import re
from google.genai import types
from core.state import NotschoolState
from tools.gemini_client import generate_with_fallback


def architect_node(state: NotschoolState) -> dict:
    """Acts as the Principal Curriculum Designer."""
    goal = state["goal"]
    image_bytes = state.get("image_bytes")
    image_mime_type = state.get("image_mime_type", "image/jpeg")
    profile = state.get("user_profile") or {}

    profile_lines = []
    if profile.get("display_name"):
        profile_lines.append(f"Learner name: {profile['display_name']}")
    if profile.get("age"):
        profile_lines.append(f"Learner age: {profile['age']}")
    if profile.get("skills"):
        profile_lines.append(f"Existing skills: {', '.join(profile['skills'][:10])}")
    if profile.get("interests"):
        profile_lines.append(f"Interests: {', '.join(profile['interests'][:10])}")
    if profile.get("learning_style"):
        profile_lines.append(f"Preferred learning style: {profile['learning_style']}")
    profile_block = ("\n    Personalisation context (tailor the plan to this learner):\n    - " +
                     "\n    - ".join(profile_lines) + "\n") if profile_lines else ""

    prompt = f"""
    You are an elite AI Professor. The user wants to learn: "{goal}".
    Design a highly actionable, structured learning roadmap. If an image of a syllabus/book index is provided, extract the topics from it!{profile_block}

    You MUST return EXACTLY this JSON structure and nothing else. Give me a full 7-DAY curriculum:
    {{
        "title": "Learning Roadmap: {goal}",
        "modules": [
            {{"day": 1, "topic": "Fundamentals", "description": "Specific details", "duration_hours": 2}},
            {{"day": 2, "topic": "Deep Dive", "description": "Specific details", "duration_hours": 3}},
            {{"day": 3, "topic": "Practice", "description": "Specific details", "duration_hours": 2}},
            {{"day": 4, "topic": "Advanced Concepts", "description": "Specific details", "duration_hours": 3}},
            {{"day": 5, "topic": "Real-world Application", "description": "Specific details", "duration_hours": 4}},
            {{"day": 6, "topic": "Project Building", "description": "Specific details", "duration_hours": 4}},
            {{"day": 7, "topic": "Review & Next Steps", "description": "Specific details", "duration_hours": 2}}
        ],
        "search_queries": ["{goal} basics tutorial full course 2026", "{goal} project tutorial 2026", "Advanced {goal} concepts 2026"],
        "certifications": ["Relevant Cert to aim for"],
        "initiatives": [
            {{"title": "Real 2026 program / cohort / bootcamp directly relevant to {goal}", "description": "One sentence on what it offers and who it is for", "type": "cohort", "provider": "Google", "url": "https://grow.google"}},
            {{"title": "Another current 2026 industry initiative", "description": "One sentence", "type": "bootcamp", "provider": "Amazon", "url": "https://aws.amazon.com"}}
        ]
    }}

    For the "initiatives" field: list 5-7 REAL, currently-running or 2026-cohort industry programs/cohorts/bootcamps/hackathons/certifications that are HIGHLY relevant to "{goal}".
    HARD REQUIREMENT: at least three of the entries MUST be flagship initiatives by Google, Amazon (AWS), or Microsoft for 2026 — e.g. Google ML Bootcamp 2026, Google Gen AI APAC, Google for Startups Accelerator, Google Cloud Skills Boost, AWS Machine Learning Engineer Nanodegree, AWS DeepRacer, AWS re/Start, Microsoft Learn AI Skills Challenge, Microsoft AI Tour, Microsoft Founders Hub, GitHub Copilot Bootcamp, Azure AI Engineer cert, etc. Pick the ones that genuinely fit "{goal}".
    Other entries can be from DeepLearning.AI, fast.ai, Kaggle, NPTEL, Smart India Hackathon, Coursera specializations, Udacity Nanodegrees, etc.
    Always set `provider` to the actual organization (Google / Amazon / Microsoft / DeepLearning.AI / Kaggle / etc.). `type` must be one of: cohort, bootcamp, certification, hackathon, program. Use REAL homepage URLs whenever you know them — never use placeholder example.com domains in the final output.
    """

    if image_bytes:
        contents = types.Content(
            role="user",
            parts=[
                types.Part(text=prompt),
                types.Part.from_bytes(data=image_bytes, mime_type=image_mime_type)
            ]
        )
    else:
        contents = prompt

    curriculum = None
    try:
        raw_text = generate_with_fallback(
            contents,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        curriculum = json.loads(match.group(0)) if match else json.loads(raw_text)
    except Exception as e:
        print(f"All retries exhausted or fatal error: {e}. Triggering Fallback.")
        curriculum = {
            "title": f"Fallback Plan for {goal}",
            "modules": [
                {"day": 1, "topic": "Fundamentals", "description": "Review basics", "duration_hours": 2},
                {"day": 2, "topic": "Core Concepts", "description": "Deep dive", "duration_hours": 3},
                {"day": 3, "topic": "Practice", "description": "Hands-on", "duration_hours": 2},
                {"day": 4, "topic": "Advanced Topics", "description": "Complex areas", "duration_hours": 3},
                {"day": 5, "topic": "Project", "description": "Build something", "duration_hours": 4},
                {"day": 6, "topic": "Review", "description": "Test knowledge", "duration_hours": 2},
                {"day": 7, "topic": "Next Steps", "description": "Plan future", "duration_hours": 1},
            ],
            "search_queries": [f"{goal} full course 2026", f"Advanced {goal} tutorial"],
            "certifications": ["Industry Standard Certification"],
            "initiatives": _fallback_initiatives(goal),
        }

    # Normalize initiatives: support both old `opportunities` and new `initiatives` keys,
    raw_inits = curriculum.get("initiatives") or curriculum.get("opportunities") or []
    cleaned = _clean_initiatives(raw_inits)
    if len(cleaned) < 3:
        cleaned = (cleaned + _fallback_initiatives(goal))[:8]
    curriculum["initiatives"] = cleaned
    # Keep legacy key in sync so older clients still render something.
    curriculum["opportunities"] = cleaned

    return {
        "curriculum_json": curriculum,
        "messages": [{"role": "system", "content": "Architect designed a learning plan with rich metadata."}]
    }


def _clean_initiatives(items):
    """Drop placeholder example.com entries and normalise shape."""
    out = []
    seen_titles = set()
    for it in items or []:
        if not isinstance(it, dict):
            continue
        title = (it.get("title") or "").strip()
        url = (it.get("url") or "").strip()
        if not title:
            continue
        if "example.com" in url.lower() or "example.org" in url.lower():
            url = ""
        key = title.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        out.append({
            "title": title,
            "description": (it.get("description") or "").strip(),
            "type": (it.get("type") or "program").strip().lower() or "program",
            "provider": (it.get("provider") or "").strip(),
            "url": url,
        })
    return out


def _fallback_initiatives(goal: str):
    """Curated, hand-checked 2026 cohorts so the panel always has something
    credible from Google / Amazon / Microsoft even if Gemini is rate-limited."""
    return [
        {
            "title": "Google ML Bootcamp 2026",
            "description": f"Google's flagship ML bootcamp — relevant prep for {goal}. APAC + India cohorts open in 2026.",
            "type": "cohort",
            "provider": "Google",
            "url": "https://rsvp.withgoogle.com/events/google-machine-learning-bootcamp",
        },
        {
            "title": "Google Cloud Skills Boost — 2026 Learning Paths",
            "description": "Hands-on labs and quests on Google Cloud, AI, and data — pick the path matching your goal.",
            "type": "program",
            "provider": "Google",
            "url": "https://www.cloudskillsboost.google",
        },
        {
            "title": "AWS Machine Learning Engineer Nanodegree (2026)",
            "description": "AWS-Udacity scholarship program covering MLOps, SageMaker, and production ML.",
            "type": "bootcamp",
            "provider": "Amazon",
            "url": "https://www.udacity.com/course/aws-machine-learning-engineer-nanodegree--nd189",
        },
        {
            "title": "AWS re/Start 2026 Cohort",
            "description": "12-week full-time AWS cloud career launchpad for learners new to tech.",
            "type": "cohort",
            "provider": "Amazon",
            "url": "https://aws.amazon.com/training/restart/",
        },
        {
            "title": "Microsoft Learn AI Skills Fest 2026",
            "description": "Free guided learning paths and certifications across Azure AI, Copilot, and data.",
            "type": "program",
            "provider": "Microsoft",
            "url": "https://learn.microsoft.com/en-us/training/",
        },
        {
            "title": "Microsoft AI Tour 2026",
            "description": "Global hands-on AI workshops for builders — registration opens by region.",
            "type": "program",
            "provider": "Microsoft",
            "url": "https://envision.microsoft.com/en-US/AITour",
        },
        {
            "title": "Kaggle Competitions & Learn",
            "description": f"Live competitions and micro-courses to ship a portfolio project for {goal}.",
            "type": "hackathon",
            "provider": "Kaggle",
            "url": "https://www.kaggle.com/competitions",
        },
    ]
