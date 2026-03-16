"""
Shared input parsers for height and weight.
Accept both metric (cm, kg) and imperial (feet/inches, lbs) input.
All values are stored internally in metric.
"""
import re


def parse_height_cm(text: str) -> tuple[float, str] | tuple[None, None]:
    """
    Parse height from free text. Returns (cm_value, display_label) or (None, None).

    Accepted formats:
        cm:    175  |  175cm  |  175 cm
        ft/in: 5'11"  |  5'11  |  5ft 11in  |  5 feet 11 inches  |  5 foot 11
               5'  (feet only)  |  6ft
    """
    text = text.lower().strip()

    # Feet + inches:  5'11"  |  5ft11in  |  5 feet 11 inches  |  5'11
    m = re.search(
        r"(\d+)\s*(?:'|ft\.?|feet|foot)\s*(\d+)?\s*(?:\"|\"|in\.?|inch(?:es)?)?",
        text,
    )
    if m:
        feet = int(m.group(1))
        inches = int(m.group(2)) if m.group(2) else 0
        cm = round(feet * 30.48 + inches * 2.54, 1)
        if 100 <= cm <= 250:
            inch_part = f" {inches}\"" if inches else ""
            return cm, f"{feet}'{inches}\" ({cm} cm)"

    # Just feet with decimal:  5.9ft  |  6.1 feet
    m = re.search(r"(\d+\.\d+)\s*(?:ft\.?|feet|foot)", text)
    if m:
        cm = round(float(m.group(1)) * 30.48, 1)
        if 100 <= cm <= 250:
            return cm, f"{cm} cm"

    # Centimetres explicit:  175cm  |  175 cm
    m = re.search(r"(\d+(?:\.\d+)?)\s*cm", text)
    if m:
        cm = round(float(m.group(1)), 1)
        if 100 <= cm <= 250:
            return cm, f"{cm} cm"

    # Bare number → treat as cm
    m = re.fullmatch(r"(\d+(?:\.\d+)?)", text)
    if m:
        val = round(float(m.group(1)), 1)
        if 100 <= val <= 250:
            return val, f"{val} cm"

    return None, None


def parse_weight_kg(text: str) -> tuple[float, str] | tuple[None, None]:
    """
    Parse weight from free text. Returns (kg_value, display_label) or (None, None).

    Accepted formats:
        kg:  85  |  85kg  |  85.5 kg
        lbs: 187lbs  |  187 lb  |  187 pounds  |  187.5lbs
    """
    text = text.lower().strip()

    # Pounds / lbs:  187lbs  |  187 lb  |  187 pounds
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)", text)
    if m:
        lbs = float(m.group(1))
        kg = round(lbs * 0.453592, 1)
        if 30 <= kg <= 300:
            return kg, f"{lbs:.1f} lbs ({kg} kg)"

    # Kilograms explicit:  85kg  |  85.5 kg
    m = re.search(r"(\d+(?:\.\d+)?)\s*kgs?", text)
    if m:
        kg = round(float(m.group(1)), 1)
        if 30 <= kg <= 300:
            return kg, f"{kg} kg"

    # Bare number → treat as kg
    m = re.fullmatch(r"(\d+(?:\.\d+)?)", text)
    if m:
        val = round(float(m.group(1)), 1)
        if 30 <= val <= 300:
            return val, f"{val} kg"

    return None, None
