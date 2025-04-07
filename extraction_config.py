import re
from typing import Dict, List, Optional, Tuple

# --- Define regex patterns ---
patterns = {
    "material": re.compile(
        r"\b(STL|Steel|SS\s?(304|316)?|Al(?:uminum)?\s?6061|Brass|Bronze|ABS|PEEK)\b",
        re.I,
    ),
    "finish": re.compile(
        r"\b(Anodized|Black Oxide|Powder Coat|Zinc Plated|Hot Dip|Ra\s?\d+(\.\d+)?(\s?(μm|um|microns)?))\b",
        re.I,
    ),
    "general_tolerance": re.compile(r"(±|\+/-)\s?\d+(\.\d+)?(\s?(mm|in|inch)?)", re.I),
    "surface_roughness": re.compile(r"Ra\s?\d+(\.\d+)?\s?(μm|um|microns)?", re.I),
    "threads": re.compile(
        r"\b(M\d+(\.\d+)?(x\d+(\.\d+)?)?|UNC\s?\d+-\d+|UNF\s?\d+-\d+|BSPT|NPT)\b", re.I
    ),
    "diameters": re.compile(r"(⌀|\bDIA\b)\s?\d+(\.\d+)?", re.I),
    "weld_notes": re.compile(r"\bWELD(ING)?\b.*", re.I),
    "standards": re.compile(r"\b(AWS|ASME|ASTM|DIN|SAES|AMSS|ISO)-?[A-Z0-9]+\b", re.I),
}


# --- Classification Criteria ---
def classify_diameter(value: str) -> Optional[List[str]]:
    """Classify pipe diameters into categories based on size ranges."""
    # Extract numeric value and unit
    matches = re.finditer(r"(\d+(?:\.\d+)?)\s*(mm|in|inch)?", value, re.IGNORECASE)
    classifications = set()

    for match in matches:
        size, unit = float(match.group(1)), match.group(2) or "mm"

        # Convert to inches for consistent comparison
        if unit.lower() in ["mm", "millimeter"]:
            size = size / 25.4

        if 6 <= size <= 8:
            classifications.add("Class A Pipe")
        elif 8 < size <= 10:
            classifications.add("Class B Pipe")
        elif 10 < size <= 12:
            classifications.add("Class C Pipe")

    return list(classifications) if classifications else None


def classify_thread(value: str) -> Optional[str]:
    """Classify threads based on size and type."""
    # Extract numeric value and type
    size_matches = re.finditer(r"(\d+(?:\.\d+)?)\s*(mm|in|inch)?", value)
    type_match = re.search(r"(Stud|Anchor|Hole|Bolt)", value, re.I)
    classifications = set()

    thread_type = type_match.group(1).lower() if type_match else "unknown"

    for match in size_matches:
        size, unit = float(match.group(1)), match.group(2) or "mm"

        # Convert to mm for consistent comparison
        if unit in ["in", "inch"]:
            size = size * 25.4

        if thread_type == "stud":
            if size <= 20:
                classifications.add("Light Duty Stud")
            else:
                classifications.add("Heavy Duty Stud")
        elif thread_type == "anchor":
            if size <= 25:
                classifications.add("Standard Anchor")
            else:
                classifications.add("Heavy Duty Anchor")
        elif thread_type == "hole":
            if size <= 20:
                classifications.add("Standard Hole")
            else:
                classifications.add("Large Hole")

    return list(classifications) if classifications else None


def classify_material(value: str) -> Optional[str]:
    """Classify materials based on type and grade."""
    value = value.upper()

    if "STAINLESS" in value or "SS" in value:
        if "304" in value:
            return "Standard Stainless"
        elif "316" in value:
            return "Marine Grade Stainless"
        return "General Stainless"
    elif "ALUMINUM" in value or "AL" in value:
        if "6061" in value:
            return "Aircraft Grade Aluminum"
        return "General Aluminum"
    elif "BRASS" in value:
        return "Decorative/Corrosion Resistant"
    elif "BRONZE" in value:
        return "High Strength/Corrosion Resistant"
    elif "PEEK" in value:
        return "High Performance Plastic"
    return None


# Classification mapping for each field type
CLASSIFICATION_MAPPING = {
    "diameters": classify_diameter,
    "threads": classify_thread,
    "material": classify_material,
}

# Classification colors for UI
CLASSIFICATION_COLORS = {
    # Pipe classifications
    "Class A Pipe": "#FF6B6B",  # Light red
    "Class B Pipe": "#4ECDC4",  # Teal
    "Class C Pipe": "#45B7D1",  # Blue
    # Thread classifications
    "Light Duty Stud": "#98D8AA",  # Light green
    "Heavy Duty Stud": "#3C6255",  # Dark green
    "Standard Anchor": "#FFD93D",  # Yellow
    "Heavy Duty Anchor": "#FF8400",  # Orange
    "Standard Hole": "#A8DF8E",  # Light green
    "Large Hole": "#86A789",  # Dark green
    # Material classifications
    "Standard Stainless": "#B2B2B2",  # Light gray
    "Marine Grade Stainless": "#7D7C7C",  # Dark gray
    "General Stainless": "#9B9B9B",  # Medium gray
    "Aircraft Grade Aluminum": "#C0C0C0",  # Silver
    "General Aluminum": "#D3D3D3",  # Light silver
    "Decorative/Corrosion Resistant": "#DAA520",  # Golden
    "High Strength/Corrosion Resistant": "#CD7F32",  # Bronze
    "High Performance Plastic": "#E6E6FA",  # Lavender
}

# --- Schema Definition ---
shared_schema = {
    "type": "object",
    "properties": {
        "material": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "value": {"type": "string"},
                            "context": {"type": "string"},
                        },
                        "required": ["text", "value", "context"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["values", "notes", "sources"],
            "additionalProperties": False,
        },
        "finish": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "value": {"type": "string"},
                            "context": {"type": "string"},
                        },
                        "required": ["text", "value", "context"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["values", "notes", "sources"],
            "additionalProperties": False,
        },
        "general_tolerance": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "value": {"type": "string"},
                            "context": {"type": "string"},
                        },
                        "required": ["text", "value", "context"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["values", "notes", "sources"],
            "additionalProperties": False,
        },
        "surface_roughness": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "value": {"type": "string"},
                            "context": {"type": "string"},
                        },
                        "required": ["text", "value", "context"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["values", "notes", "sources"],
            "additionalProperties": False,
        },
        "threads": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "value": {"type": "string"},
                            "context": {"type": "string"},
                        },
                        "required": ["text", "value", "context"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["values", "notes", "sources"],
            "additionalProperties": False,
        },
        "diameters": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "value": {"type": "string"},
                            "context": {"type": "string"},
                        },
                        "required": ["text", "value", "context"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["values", "notes", "sources"],
            "additionalProperties": False,
        },
        "weld_requirements": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "value": {"type": "string"},
                            "context": {"type": "string"},
                        },
                        "required": ["text", "value", "context"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["values", "notes", "sources"],
            "additionalProperties": False,
        },
        "standards": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "value": {"type": "string"},
                            "context": {"type": "string"},
                        },
                        "required": ["text", "value", "context"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["values", "notes", "sources"],
            "additionalProperties": False,
        },
        "cost_drivers": {
            "type": "object",
            "properties": {
                "values": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string"},
                            "value": {"type": "string"},
                            "context": {"type": "string"},
                        },
                        "required": ["text", "value", "context"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["values", "notes", "sources"],
            "additionalProperties": False,
        },
    },
    "required": [
        "material",
        "finish",
        "general_tolerance",
        "surface_roughness",
        "threads",
        "diameters",
        "weld_requirements",
        "standards",
        "cost_drivers",
    ],
    "additionalProperties": False,
}
