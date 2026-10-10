from app.domain.text import TextFingerprinter


class StateCodes:
    """Indian state / union-territory names ↔ two-letter codes, tolerant of old and alternate names."""

    NAMES = {
        "AN": "Andaman and Nicobar Islands", "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh",
        "AS": "Assam", "BR": "Bihar", "CH": "Chandigarh", "CT": "Chhattisgarh",
        "DN": "Dadra and Nagar Haveli and Daman and Diu", "DL": "Delhi", "GA": "Goa",
        "GJ": "Gujarat", "HR": "Haryana", "HP": "Himachal Pradesh", "JK": "Jammu and Kashmir",
        "JH": "Jharkhand", "KA": "Karnataka", "KL": "Kerala", "LA": "Ladakh", "LD": "Lakshadweep",
        "MP": "Madhya Pradesh", "MH": "Maharashtra", "MN": "Manipur", "ML": "Meghalaya",
        "MZ": "Mizoram", "NL": "Nagaland", "OR": "Odisha", "PY": "Puducherry", "PB": "Punjab",
        "RJ": "Rajasthan", "SK": "Sikkim", "TN": "Tamil Nadu", "TG": "Telangana", "TR": "Tripura",
        "UP": "Uttar Pradesh", "UT": "Uttarakhand", "WB": "West Bengal",
    }
    _ALIASES = {
        "orissa": "OR", "uttaranchal": "UT", "pondicherry": "PY", "nct of delhi": "DL",
        "national capital territory of delhi": "DL", "chattisgarh": "CT", "dadra and nagar haveli": "DN",
        "daman and diu": "DN", "andaman and nicobar": "AN", "jammu kashmir": "JK", "tamilnadu": "TN",
    }
    @classmethod
    def code(cls, name: str | None) -> str | None:
        if not name:
            return None
        return _BY_NAME.get(_FP.norm_name(name.replace("&", " and ")))

    @classmethod
    def name(cls, code: str) -> str | None:
        return cls.NAMES.get(code)


# Built at module level: comprehensions inside a class body cannot see class attributes.
_FP = TextFingerprinter()
_BY_NAME = {_FP.norm_name(v): k for k, v in StateCodes.NAMES.items()} | StateCodes._ALIASES
