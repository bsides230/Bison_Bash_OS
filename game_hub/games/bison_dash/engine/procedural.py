import random
import uuid

BISON_FIRST_NAMES = [
    "Thunder", "Lightning", "Stomper", "Grassy", "Duke", "Titan", "Blaze", "Charger", "Shadow", "Ranger"
]

BISON_LAST_NAMES = [
    "Hooves", "Horns", "Stampede", "Runner", "Strider", "Meadow", "Prairie", "Dash", "Crusher", "Sprint"
]

def generate_bison(slot_id: int) -> dict:
    """Generates a procedural bison profile with scaled stats."""

    first_name = random.choice(BISON_FIRST_NAMES)
    last_name = random.choice(BISON_LAST_NAMES)
    full_name = f"{first_name} {last_name}"

    # Stats scaled down slightly so they don't overpower the huge dice variants.
    # Launch: D20 + Jockey Reaction
    # Back Straightaway: D1000 + Bison Speed
    # Curved Corners: D6 + Bison Cornering
    # Home Stretch: D100 + Bison Stamina

    jockey_reaction = random.randint(1, 10)     # Modifies D20
    bison_speed = random.randint(1, 200)        # Modifies D1000
    bison_cornering = random.randint(1, 3)      # Modifies D6
    bison_stamina = random.randint(1, 30)       # Modifies D100

    return {
        "id": f"bison_{slot_id}_{uuid.uuid4().hex[:6]}",
        "slot": slot_id,
        "name": full_name,
        "color": _get_color_for_slot(slot_id),
        "stats": {
            "jockey_reaction": jockey_reaction,
            "bison_speed": bison_speed,
            "bison_cornering": bison_cornering,
            "bison_stamina": bison_stamina
        }
    }

def _get_color_for_slot(slot_id: int) -> str:
    # Colors for the placeholder frontend rects
    colors = {
        1: "#FF0000", # Red
        2: "#00FF00", # Green
        3: "#0000FF", # Blue
        4: "#FFFF00", # Yellow
        5: "#FF00FF", # Magenta
        6: "#00FFFF"  # Cyan
    }
    return colors.get(slot_id, "#FFFFFF")

def initialize_lineup() -> list:
    """Generates a fresh lineup of 6 bison."""
    return [generate_bison(i) for i in range(1, 7)]
