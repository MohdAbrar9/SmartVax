"""
chatbot_utils.py
----------------
Talks to Anthropic's Claude API to answer parents' vaccine questions.

Why a fallback? During your project demo, the venue's WiFi might be
down or you might forget to set the API key — so if the AI call
fails for ANY reason, we quietly fall back to a small set of
pre-written answers about common vaccine questions. This means your
live demo never shows a broken chatbot.
"""

import os
import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# System prompt: tells the AI what role to play and how to behave.
SYSTEM_PROMPT = (
    "You are 'Vaccine Assistant', a friendly chatbot inside a child "
    "vaccination tracking app used by parents in India. Answer "
    "questions about vaccines, side effects, and schedules in short, "
    "simple, reassuring language (3-5 sentences max). If a question "
    "sounds like a medical emergency, tell the user to contact a "
    "doctor or ASHA worker immediately instead of answering yourself."
)

# Offline fallback answers, used only if the API call fails.
FALLBACK_ANSWERS = {
    "side effect": (
        "Common side effects may include mild fever, redness or "
        "swelling at the injection site, irritability, and loss of "
        "appetite. These usually go away in 1-2 days. Contact your "
        "doctor if fever is high or symptoms last longer."
    ),
    "missed": (
        "If you missed a dose, don't panic — most vaccines can still "
        "be given late. Contact your nearest ASHA worker or PHC to "
        "reschedule as soon as possible."
    ),
    "pentavalent": (
        "The Pentavalent vaccine protects against five diseases: "
        "Diphtheria, Pertussis (whooping cough), Tetanus, Hepatitis B, "
        "and Hib (a cause of pneumonia and meningitis). It is given "
        "in 3 doses at 6, 10, and 14 weeks."
    ),
    "default": (
        "I'm currently offline, but here's a general tip: always keep "
        "your child's vaccination card safe and consult your ASHA "
        "worker or doctor for specific medical advice."
    ),
}


def get_fallback_answer(question):
    """Picks the closest offline answer based on keywords in the question."""
    question_lower = question.lower()
    for keyword, answer in FALLBACK_ANSWERS.items():
        if keyword in question_lower:
            return answer
    return FALLBACK_ANSWERS["default"]


def ask_chatbot(question):
    """
    Sends the parent's question to Claude and returns the answer text.
    Falls back to a canned answer if the API key is missing or the
    request fails for any reason (no internet, rate limit, etc).
    """
    if not ANTHROPIC_API_KEY:
        return get_fallback_answer(question)

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 300,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": question}],
    }

    try:
        response = requests.post(
            ANTHROPIC_URL, headers=headers, json=payload, timeout=10
        )
        response.raise_for_status()
        data = response.json()
        # data["content"] is a list of blocks; we want the text block.
        answer = "".join(
            block["text"] for block in data["content"] if block["type"] == "text"
        )
        return answer.strip()
    except Exception as e:
        print(f"[chatbot_utils.py] AI call failed, using fallback: {e}")
        return get_fallback_answer(question)
