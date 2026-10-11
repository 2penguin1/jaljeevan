"""What a relief brief may recommend, per hazard, and the rule that keeps numbers out of AI-written text.

The AI picks action keys from this fixed menu (it cannot invent a plan) and writes plain words; every number in a brief
is computed in code and shown in its own table.
"""
import re

PLAYBOOK: dict[str, dict[str, str]] = {
    "drought": {
        "tanker_rounds": "Start daily drinking-water tanker rounds to the worst-hit villages",
        "fodder_camps": "Open fodder and water camps for cattle",
        "borewell_repair": "Repair and deepen public borewells and handpumps",
        "loan_relief": "Pause farm-loan recovery and speed up crop-loss payments",
        "work_schemes": "Open MGNREGA work sites near affected villages",
        "water_audit": "Check reservoir and well levels weekly and ration supply fairly",
    },
    "water": {
        "tanker_rounds": "Run drinking-water tankers to wards without piped supply",
        "pipeline_repair": "Repair broken mains and restore the supply schedule",
        "supply_schedule": "Publish a ward-wise water timetable and stick to it",
        "water_quality": "Test supplied water and chlorinate where needed",
    },
    "flood": {
        "evacuation": "Move people from low-lying areas to relief camps",
        "relief_camps": "Run relief camps with food, drinking water and medicine",
        "clean_water": "Supply safe drinking water and chlorine tablets",
        "health_teams": "Send health teams to prevent water-borne disease",
    },
    "heat": {
        "cooling_centres": "Open cooling centres and drinking-water points",
        "work_hours": "Shift outdoor work away from the hottest hours",
        "health_alerts": "Alert hospitals and keep heatstroke beds ready",
        "water_points": "Set up free drinking-water points at markets and bus stands",
    },
}

_DIGIT = re.compile(r"\d")  # \d matches Indian digits (२५) too
# numbers written as words are numbers too ("twenty thousand villagers")
_NUMBER_WORD = re.compile(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|"
                          r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundreds?|thousands?|lakhs?|crores?|"
                          r"millions?|billions?|dozens?|half|percent)\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?।])\s+")


def keep_actions(hazard: str, keys: list[str]) -> list[str]:
    allowed = PLAYBOOK.get(hazard, {})
    return list(dict.fromkeys(k for k in keys if k in allowed))


def without_numbers(text: str) -> str:
    """Drop every sentence that contains a digit: numbers in a brief come from code, never from the AI."""
    return " ".join(s for s in _SENTENCE.split((text or "").strip())
                    if s and not _DIGIT.search(s) and not _NUMBER_WORD.search(s))
