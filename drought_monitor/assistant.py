"""Plain-language answers for the dashboard, with optional Claude.

The page always has a local answer. Claude is used only when a key is set.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from drought_monitor.env import load_local_env

load_local_env()

RISK_RANGES = "Low is 0–39.9, Medium is 40–64.9, and High is 65–100"
SYSTEM_PROMPT = (
    "Answer only from the provided dashboard data, in plain language for a "
    "non-expert. Do not invent measurements, dates, or causes. If the data does "
    "not contain the answer, say that it is not known from this page."
)
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5"
NO_KEY_NOTICE = (
    "No language-model key is set. Add ANTHROPIC_API_KEY in Streamlit Cloud > "
    "App settings > Secrets. Optional ANTHROPIC_MODEL defaults to "
    f"{DEFAULT_ANTHROPIC_MODEL}. Until then, answers come only from the numbers "
    "on this page."
)
EARTHDATA_SIGNUP = "https://urs.earthdata.nasa.gov"


def _setting(name: str) -> str | None:
    value = os.environ.get(name)
    if value and value.strip():
        return value.strip()
    try:
        import streamlit as st

        secret = st.secrets.get(name)
    except Exception:
        return None
    if secret:
        text = str(secret).strip()
        return text or None
    return None


def earthdata_credentials_present() -> bool:
    """True when a token, or both an Earthdata username and password, is set."""

    if _setting("EARTHDATA_TOKEN"):
        return True
    return bool(_setting("EARTHDATA_USERNAME") and _setting("EARTHDATA_PASSWORD"))


def earthdata_token_notice(using_mock: bool) -> str:
    """Startup copy shown when NASA download credentials are absent."""

    if using_mock:
        lead = "This view is using mock data."
    else:
        lead = (
            "Public NASA POWER rainfall and soil wetness, and Copernicus slope, "
            "are loaded. The burn mask is still mock."
        )
    return (
        f"{lead} Real NISAR file downloads need a free Earthdata Login token. "
        f"Create one at {EARTHDATA_SIGNUP}, then add EARTHDATA_TOKEN in "
        "Streamlit Cloud > App settings > Secrets and reboot the app."
    )


def llm_provider() -> str | None:
    """Claude when ANTHROPIC_API_KEY is set, otherwise the on-page answer."""

    if _setting("ANTHROPIC_API_KEY"):
        return "claude"
    return None


_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _month_number(label: str) -> int:
    lowered = label.lower()
    for name, number in _MONTHS.items():
        if name in lowered:
            return number
    if len(label) >= 7 and label[4:5] == "-":
        try:
            return int(label[5:7])
        except ValueError:
            return 6
    return 6


def _is_southern(latitude: float | None, coordinates: str) -> bool:
    if latitude is not None:
        return latitude < 0
    head = coordinates.split(",")[0]
    return "S" in head


def season_notes(slider_date: str, latitude: float | None, coordinates: str) -> tuple[str, str]:
    """Local season, and the farm work that season usually means."""

    month = _month_number(slider_date)
    southern = _is_southern(latitude, coordinates)
    if month in (12, 1, 2):
        season = "summer" if southern else "winter"
    elif month in (3, 4, 5):
        season = "autumn" if southern else "spring"
    elif month in (6, 7, 8):
        season = "winter" if southern else "summer"
    else:
        season = "spring" if southern else "autumn"
    harvest = (not southern and month in (8, 9, 10, 11)) or (southern and month in (11, 12, 1, 2, 3))
    if harvest:
        return (
            f"It is {season}, and farmers are in harvest.",
            "A farmer in harvest season times water from the rain and soil.",
        )
    if season in {"spring", "autumn"} and month in (3, 4, 5, 9, 10):
        return (
            f"It is {season}, when many farmers are planting.",
            "A farmer at planting times the first water from the rain and soil.",
        )
    if season == "summer":
        return (
            f"It is {season}, and growers are irrigating.",
            "A farmer mid-season uses the rain and soil to plan irrigation.",
        )
    return (
        f"It is {season}, a quieter stretch for many crops.",
        "A farmer in the off-season uses the rain and soil to plan stored water.",
    )


def build_context(
    *,
    site_name: str,
    coordinates: str,
    slider_date: str,
    rain_month: str,
    percent_normal: float,
    anomaly_mm: float,
    climatology_name: str,
    soil_value: float,
    soil_unit: str,
    soil_first: float,
    risk_score: float,
    risk_class: str,
    burned_percent: float,
    mean_slope: float,
    source_mode: str,
    using_mock: bool,
    latitude: float | None = None,
) -> dict:
    """Compact facts the chat and summary are allowed to use."""

    if not soil_unit:
        trend = "unavailable for this box"
    elif soil_value > soil_first + 0.01:
        trend = "higher than the first scene in the series"
    elif soil_value < soil_first - 0.01:
        trend = "lower than the first scene in the series"
    else:
        trend = "about the same as the first scene in the series"
    if using_mock:
        source_sentence = "The numbers on this view are seeded mock data, not a live satellite download."
        source_clause = "seeded mock data rather than a live satellite download"
    else:
        source_sentence = (
            "Rainfall and soil wetness are NASA POWER values, slope is Copernicus DEM, "
            "and the burn mask is still a seeded mock layer."
        )
        source_clause = (
            "NASA POWER rainfall and soil wetness, Copernicus slope, and a still-mock burn mask"
        )
    opening, farm_line = season_notes(slider_date, latitude, coordinates)
    if "lower than" in trend:
        soil_short = "down since the first scene"
    elif "higher than" in trend:
        soil_short = "up since the first scene"
    else:
        soil_short = "about the same as the first scene"
    return {
        "site_name": site_name,
        "coordinates": coordinates,
        "slider_date": slider_date,
        "rain_month": rain_month,
        "percent_normal": percent_normal,
        "anomaly_mm": anomaly_mm,
        "climatology_name": climatology_name,
        "soil_value": soil_value,
        "soil_unit": soil_unit,
        "soil_first": soil_first,
        "soil_trend": trend,
        "soil_short": soil_short,
        "season_opening": opening,
        "farm_line": farm_line,
        "risk_score": risk_score,
        "risk_class": risk_class,
        "risk_ranges": RISK_RANGES,
        "burned_percent": burned_percent,
        "mean_slope": mean_slope,
        "source_mode": source_mode,
        "using_mock": using_mock,
        "source_sentence": source_sentence,
        "source_clause": source_clause,
        "sediment_warning": sediment_warning(risk_class),
        "glossary": (
            "Percent of normal is observed rainfall divided by the named climatology "
            "for that month. The millimetre delta is observed minus climatology; "
            "negative means a deficit. The rainfall card uses the latest rainfall "
            "month and does not follow the slider. The red dotted line is the slider date. "
            f"Runoff classes: {RISK_RANGES}. The index is 50% slope, 32% wetness, and 18% burn flag."
        ),
    }


def context_block(context: dict) -> str:
    return "\n".join(
        [
            f"Site: {context['site_name']} ({context['coordinates']})",
            f"Slider date: {context['slider_date']}",
            (
                f"Rainfall: {context['rain_month']} is {context['percent_normal']:.0f}% of "
                f"{context['climatology_name']}, anomaly {context['anomaly_mm']:+.0f} mm"
            ),
            (
                "Soil moisture: data unavailable"
                if not context["soil_unit"]
                else (
                    f"Soil moisture: {context['soil_value']:.3f} {context['soil_unit']} "
                    f"on the slider date, {context['soil_trend']}"
                )
            ),
            (
                f"Runoff risk: {context['risk_class']}, index {context['risk_score']:.0f}/100. "
                f"Ranges: {context['risk_ranges']}"
            ),
            f"Burned pixels: {context['burned_percent']:.1f}%",
            f"Mean slope: {context['mean_slope']:.1f} degrees",
            f"Sediment warning: {context['sediment_warning']}",
            f"Data source: {context['source_sentence']}",
            f"Glossary: {context['glossary']}",
        ]
    )


def sediment_warning(risk_class: str) -> str:
    if risk_class == "High":
        return (
            "Elevated runoff and erosion signal: steep or burned ground overlaps "
            "wetter cells, so sediment can move after rain."
        )
    if risk_class == "Medium":
        return "Watch for sediment: some steep or burned cells may mobilise soil after rain."
    return (
        "The scene-average runoff signal is lower, so widespread sediment movement "
        "is less likely, though local steep cells can still respond to rain."
    )


def template_summary(context: dict) -> str:
    """Four to six sentences a visitor can read without an API key."""

    sentences = [
        (
            f"On {context['slider_date']}, {context['site_name']} "
            f"({context['coordinates']}) is shown with {context['source_clause']}."
        ),
        (
            f"Rainfall for {context['rain_month']} is {context['percent_normal']:.0f}% of the "
            f"{context['climatology_name']}, which is {context['anomaly_mm']:+.0f} mm compared "
            "with that same monthly baseline."
        ),
        (
            "Soil moisture data is unavailable for this box."
            if not context["soil_unit"]
            else (
                f"Soil moisture on the selected date is {context['soil_value']:.3f} {context['soil_unit']}, "
                f"{context['soil_trend']}."
            )
        ),
        (
            f"Runoff risk is {context['risk_class']}, with a scene index of "
            f"{context['risk_score']:.0f} out of 100, where {context['risk_ranges']}."
        ),
        (
            f"About {context['burned_percent']:.1f}% of the grid is flagged as burned, "
            f"and the mean slope is {context['mean_slope']:.1f} degrees."
        ),
        context["sediment_warning"],
    ]
    return " ".join(sentences)


def fallback_answer(question: str, context: dict) -> str:
    """Keyword answer limited to the context block."""

    text = question.lower()
    answers = []
    if any(word in text for word in ("rain", "percent", "normal", "climat", "anomaly", "deficit")):
        answers.append(
            f"For {context['rain_month']}, rainfall is {context['percent_normal']:.0f}% of the "
            f"{context['climatology_name']}. The {context['anomaly_mm']:+.0f} mm figure is "
            "observed rainfall minus that climatology. A negative value is a deficit. "
            "This card does not follow the slider."
        )
    if any(word in text for word in ("soil", "moisture", "wet")):
        answers.append(
            (
                "Soil moisture data is unavailable for this box."
                if not context["soil_unit"]
                else (
                    f"On {context['slider_date']}, mean soil moisture is {context['soil_value']:.3f} "
                    f"{context['soil_unit']}, {context['soil_trend']}."
                )
            )
        )
    if any(word in text for word in ("risk", "runoff", "class", "low", "medium", "high", "index")):
        answers.append(
            f"Runoff risk is {context['risk_class']}, index {context['risk_score']:.0f} out of 100. "
            f"The ranges are {context['risk_ranges']}."
        )
    if any(word in text for word in ("burn", "fire", "scar")):
        answers.append(
            f"About {context['burned_percent']:.1f}% of the pixels are flagged as burned."
        )
    if any(word in text for word in ("slope", "steep", "terrain", "hill")):
        answers.append(f"The mean slope is {context['mean_slope']:.1f} degrees.")
    if any(word in text for word in ("sediment", "erosion", "warning")):
        answers.append(context["sediment_warning"])
    if any(word in text for word in ("mock", "real", "nasa", "source", "token", "satellite")):
        answers.append(context["source_sentence"])
    if any(word in text for word in ("date", "slider", "when", "scene")):
        answers.append(
            f"The slider date is {context['slider_date']}. The red dotted line marks that date."
        )
    if not answers and any(word in text for word in ("what", "summary", "overview", "explain", "looking")):
        answers.append(template_summary(context))
    if answers:
        return " ".join(dict.fromkeys(answers))
    return (
        "That is not known from this page. The page has the site, the slider date, "
        "rainfall versus its climatology, soil moisture, runoff risk and its class ranges, "
        "burned area, mean slope, the sediment warning, and whether the view is mock or NASA data."
    )


def answer_question(question: str, context: dict) -> tuple[str, str, str | None]:
    """Return answer text, provider, and a plain-language error. Never raises."""

    provider = llm_provider()
    if provider is None:
        return fallback_answer(question, context), "page", None
    prompt = f"{context_block(context)}\n\nQuestion: {question}"
    try:
        return _claude(prompt), "claude", None
    except Exception as exc:
        return fallback_answer(question, context), "page", _plain_model_error(exc)


def template_podcast(context: dict) -> str:
    """About 30 seconds of speech: who the reading helps, and what the numbers mean."""

    source = "This is the seeded demo" if context["using_mock"] else "This uses the loaded satellite series"
    return (
        f"{context['site_name']}, {context['slider_date']}. {context['season_opening']} "
        f"Rain is {context['percent_normal']:.0f} percent of normal. "
        f"Soil is {context['soil_short']}. "
        f"Runoff is {context['risk_class']}, {context['risk_score']:.0f} out of 100. "
        f"Burned share is {context['burned_percent']:.0f} percent, on a {context['mean_slope']:.0f} degree slope. "
        "A land buyer uses this as a dryness check. "
        f"{context['farm_line']} "
        "A fire crew watches steep burned slopes, which shed sediment after rain. "
        f"An insurer treats {context['risk_class']} as today's flag, not a promise. "
        f"{source}. This reading is not a climate forecast and not advice to buy or walk away."
    )


def podcast_script(context: dict) -> tuple[str, str, str | None]:
    """Return a spoken briefing, provider, and error. Never raises."""

    provider = llm_provider()
    if provider is None:
        return template_podcast(context), "page", None
    prompt = (
        "Write a spoken briefing of 80 to 100 words, about 30 seconds when read aloud. "
        "Sound like a person briefing a colleague, with contractions. "
        "Use only the numbers and the season notes given. "
        "Say what the rainfall, soil, runoff class, burned share, and slope mean. "
        "Say who it helps: a land buyer, a farmer in that season's work "
        "(planting, irrigation, or harvest), a fire crew, and an insurer. "
        "End by saying this is not a climate forecast and not advice to buy or walk away.\n\n"
        + context_block(context)
    )
    try:
        return _claude(prompt), "claude", None
    except Exception as exc:
        return template_podcast(context), "page", _plain_model_error(exc)


def summarize_view(context: dict) -> tuple[str, str, str | None]:
    """Return a 4–6 sentence summary, provider, and error. Never raises."""

    provider = llm_provider()
    if provider is None:
        return template_summary(context), "page", None
    prompt = (
        "Write 4 to 6 short sentences for a non-expert. Cover the slider date, "
        "rainfall versus normal, the soil-moisture trend, the runoff-risk class, "
        "burned area, the sediment warning, and whether the data is mock or real.\n\n"
        + context_block(context)
    )
    try:
        return _claude(prompt), "claude", None
    except Exception as exc:
        return template_summary(context), "page", _plain_model_error(exc)


def _plain_model_error(exc: Exception) -> str:
    detail = " ".join(str(exc).split()) or "Claude could not be reached."
    return f"{detail} The answer below uses only the numbers on this page."


def _claude(prompt: str) -> str:
    model = _setting("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL
    body = {
        "model": model,
        "max_tokens": 800,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }
    payload = _post_json(
        "https://api.anthropic.com/v1/messages",
        body,
        headers={
            "content-type": "application/json",
            "x-api-key": _setting("ANTHROPIC_API_KEY") or "",
            "anthropic-version": "2023-06-01",
        },
    )
    parts = [
        block.get("text", "")
        for block in payload.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    text = "\n".join(part.strip() for part in parts if part.strip()).strip()
    if not text:
        raise RuntimeError("Claude returned an empty answer.")
    return text


def _post_json(url: str, body: dict, headers: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={**headers, "User-Agent": "dancing-with-the-sars/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        message = _anthropic_error_message(raw) or f"Claude returned HTTP {exc.code}."
        raise RuntimeError(message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Claude could not be reached.") from exc


def _anthropic_error_message(raw: str) -> str:
    try:
        payload = json.loads(raw)
        error = payload.get("error", {})
        if isinstance(error, dict) and error.get("message"):
            return f"Claude said: {error['message']}"
    except json.JSONDecodeError:
        pass
    cleaned = " ".join(raw.split())
    if not cleaned:
        return ""
    return f"Claude returned an error: {cleaned[:180]}"
