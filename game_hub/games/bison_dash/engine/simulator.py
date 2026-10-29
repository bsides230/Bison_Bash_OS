import random
import math

# =========================================================================
# EXACT 1080P CANVAS TRACK GEOMETRY (Contained with 105px side margins)
# =========================================================================
CX1 = 1440.0       # East Turn Center (1440 + 375 = 1815px -> 105px margin on right)
CX2 = 480.0        # West Turn Center (480 - 375 = 105px -> 105px margin on left)
CY = 580.0         # Vertical Centerline (580 - 375 = 205px top, 580 + 375 = 955px bottom)
R_BASE = 260.0     # Centerline track radius
LANE_WIDTH = 35.0  # 35px per lane across all 6 lanes
START_X = 960.0    # Checkered Start / Finish line X coordinate

def roll_d20(): return random.randint(1, 20)
def roll_d1000(): return random.randint(1, 1000)
def roll_d6(): return random.randint(1, 6)
def roll_d100(): return random.randint(1, 100)

def get_lane_radius(slot: int) -> float:
    """Slot 1 (innermost, 172.5px) to Slot 6 (outermost, 347.5px)."""
    return R_BASE + (slot - 3.5) * LANE_WIDTH

def get_lane_point(slot: int, progress: float) -> tuple[float, float, float]:
    """
    Returns (x, y, heading_rad) along the true stadium oval track.
    progress is clamped in [0.0, 1.0].
    Sectors are normalized so that identical progress corresponds to identical
    advancement along the track across all lanes, ensuring 100% agreement with the live standings:
    - Sector 1 [0.00 -> 0.15]: Bottom Straight (Launch) from START_X (960) to Turn 1 IN (1440)
    - Sector 2 [0.15 -> 0.35]: Turn 1 East Curve (Corner 1 IN -> Corner 1 OUT)
    - Sector 3 [0.35 -> 0.65]: Back Straight North (Corner 1 OUT -> Corner 2 IN)
    - Sector 4 [0.65 -> 0.85]: Turn 2 West Curve (Corner 2 IN -> Corner 2 OUT)
    - Sector 5 [0.85 -> 1.00]: Home Stretch (Corner 2 OUT -> Finish Line at 960)
    """
    p = max(0.0, min(1.0, progress))
    r = get_lane_radius(slot)

    # 1. Sector 1: Bottom Straight / Launch (0.00 -> 0.15)
    if p <= 0.15:
        frac = p / 0.15
        x = START_X + frac * (CX1 - START_X)
        y = CY + r
        heading = 0.0
        return (x, y, heading)

    # 2. Sector 2: Turn 1 (East Curve: Corner 1 IN -> Corner 1 OUT) (0.15 -> 0.35)
    if p <= 0.35:
        frac = (p - 0.15) / 0.20
        angle = (math.pi / 2.0) - frac * math.pi
        x = CX1 + r * math.cos(angle)
        y = CY + r * math.sin(angle)
        heading = angle - (math.pi / 2.0)
        return (x, y, heading)

    # 3. Sector 3: Back straight (North: Corner 1 OUT -> Corner 2 IN) (0.35 -> 0.65)
    if p <= 0.65:
        frac = (p - 0.35) / 0.30
        x = CX1 - frac * (CX1 - CX2)
        y = CY - r
        heading = math.pi
        return (x, y, heading)

    # 4. Sector 4: Turn 2 (West Curve: Corner 2 IN -> Corner 2 OUT) (0.65 -> 0.85)
    if p <= 0.85:
        frac = (p - 0.65) / 0.20
        angle = -(math.pi / 2.0) - frac * math.pi
        x = CX2 + r * math.cos(angle)
        y = CY + r * math.sin(angle)
        heading = angle - (math.pi / 2.0)
        return (x, y, heading)

    # 5. Sector 5: Home stretch (South: Corner 2 OUT -> Finish Line at START_X) (0.85 -> 1.00)
    frac = (p - 0.85) / 0.15
    x = CX2 + frac * (START_X - CX2)
    y = CY + r
    heading = 0.0
    return (x, y, heading)

def simulate_race(lineup: list, duration: int = 40) -> dict:
    """
    Simulates a 40-second race using sequential tabletop D&D dice rolls per sector.
    Sector 1: The Launch (0s - 6s)    -> D20 + Jockey Reaction (with D20 wildcard)
    Sector 2: Turn 1 (6s - 16s)       -> D6 + Bison Cornering
    Sector 3: Back Stretch (16s - 28s)-> D1000 + (Bison Speed * 10)
    Sector 4: Turn 2 (28s - 34s)      -> D6 + Bison Cornering
    Sector 5: Home Stretch (34s - 40s)-> D100 + Bison Stamina
    """
    if not lineup:
        return {}

    # Sequential sector dice roll evaluation per racer
    racer_rolls = {}
    for bison in lineup:
        b_id = bison.get("id") or f"bison_{bison.get('slot', 1)}"
        stats = bison.get("stats", {})
        reaction = stats.get("jockey_reaction", 10)
        speed = stats.get("bison_speed", 65)
        cornering = stats.get("bison_cornering", 5)
        stamina = stats.get("bison_stamina", 50)

        # Stage 1: The Launch -> D20 roll + Jockey Reaction
        d20_launch = roll_d20()
        wildcard_roll = roll_d20()
        launch_bonus = 0
        if wildcard_roll == 20:
            launch_bonus = 8  # Turbo Boost out of gates!
        elif wildcard_roll == 1:
            launch_bonus = -6 # Stumble out of gates!
        score_launch = d20_launch + reaction + launch_bonus

        # Stage 2: Turn 1 East Curve -> D6 roll + Bison Cornering
        d6_turn1 = roll_d6()
        score_turn1 = d6_turn1 + cornering

        # Stage 3: Back Straightaway -> D1000 roll + (Bison Speed * 10)
        d1000_speed = roll_d1000()
        score_speed = d1000_speed + (speed * 10)

        # Stage 4: Turn 2 West Curve -> D6 roll + Bison Cornering
        d6_turn2 = roll_d6()
        score_turn2 = d6_turn2 + cornering

        # Stage 5: Home Stretch Sprint -> D100 roll + Bison Stamina
        d100_stamina = roll_d100()
        score_stamina = d100_stamina + stamina

        # Aggregate race performance weighting
        total_score = (
            score_launch * 25 +
            score_turn1 * 90 +
            score_speed +
            score_turn2 * 90 +
            score_stamina * 8
        )

        racer_rolls[b_id] = {
            "launch": score_launch,
            "turn1": score_turn1,
            "speed": score_speed,
            "turn2": score_turn2,
            "stamina": score_stamina,
            "total": total_score,
            "slot": bison.get("slot", 1),
            "bison": bison
        }

    # Tie-breaking with D6 roll-offs to ensure distinct ranks
    unique_totals = set(v["total"] for v in racer_rolls.values())
    while len(unique_totals) < len(lineup):
        for id1, d1 in racer_rolls.items():
            for id2, d2 in racer_rolls.items():
                if id1 != id2 and d1["total"] == d2["total"]:
                    r1 = roll_d6()
                    r2 = roll_d6()
                    if r1 >= r2:
                        d1["total"] += 1
                    else:
                        d2["total"] += 1
        unique_totals = set(v["total"] for v in racer_rolls.values())

    # Final leaderboard ranking by total score
    sorted_racers = sorted(racer_rolls.items(), key=lambda x: x[1]["total"], reverse=True)
    final_ranks = {b_id: rank for rank, (b_id, _) in enumerate(sorted_racers)}

    # Min/max score normalization for each sector to compute live relative speeds
    launch_scores = [v["launch"] for v in racer_rolls.values()]
    turn1_scores = [v["turn1"] for v in racer_rolls.values()]
    speed_scores = [v["speed"] for v in racer_rolls.values()]
    turn2_scores = [v["turn2"] for v in racer_rolls.values()]
    stamina_scores = [v["stamina"] for v in racer_rolls.values()]

    def norm(val, lst):
        mn, mx = min(lst), max(lst)
        return (val - mn) / max(1.0, float(mx - mn))

    # Sequential Sector Timestamps for Race (scales with duration, default 40s)
    t_s1_end = duration * 0.15  # Launch phase ends at Turn 1 IN (6.0s for 40s race)
    t_s2_end = duration * 0.40  # Turn 1 East curve ends at Turn 1 OUT (16.0s for 40s race)
    t_s3_end = duration * 0.70  # Back straightaway ends at Turn 2 IN (28.0s for 40s race)
    t_s4_end = duration * 0.85  # Turn 2 West curve ends at Turn 2 OUT (34.0s for 40s race)
    t_s5_end = float(duration)  # Home stretch ends at Finish Line (40.0s)

    telemetry = {}
    fps = 10
    total_steps = int(duration * fps)

    for b_id, r_info in racer_rolls.items():
        slot = r_info["slot"]
        rank = final_ranks[b_id]

        # Normalized performance factors in [0.0, 1.0]
        f_launch = norm(r_info["launch"], launch_scores)
        f_turn1 = norm(r_info["turn1"], turn1_scores)
        f_speed = norm(r_info["speed"], speed_scores)
        f_turn2 = norm(r_info["turn2"], turn2_scores)
        f_stamina = norm(r_info["stamina"], stamina_scores)

        telemetry[b_id] = []

        for step in range(total_steps + 1):
            t = step / fps

            # Sector-by-sector progress calculation
            # Physical sector fractions (matching track geometry 100%):
            # Sector 1 (Launch): 0.00 -> 0.15
            # Sector 2 (Turn 1): 0.15 -> 0.35
            # Sector 3 (Back):   0.35 -> 0.65
            # Sector 4 (Turn 2): 0.65 -> 0.85
            # Sector 5 (Home):   0.85 -> 1.00
            if t <= t_s1_end:
                # Stage 1: The Launch (0.00 -> 0.15)
                frac = t / t_s1_end
                var = (f_launch - 0.5) * 0.02 * math.sin(frac * math.pi)
                progress = 0.0 + (frac * 0.15) + var
            elif t <= t_s2_end:
                # Stage 2: Turn 1 East Semicircle (0.15 -> 0.35)
                frac = (t - t_s1_end) / (t_s2_end - t_s1_end)
                var = (f_turn1 - 0.5) * 0.025 * math.sin(frac * math.pi)
                progress = 0.15 + (frac * 0.20) + var
            elif t <= t_s3_end:
                # Stage 3: Back Straightaway North (0.35 -> 0.65)
                frac = (t - t_s2_end) / (t_s3_end - t_s2_end)
                var = (f_speed - 0.5) * 0.03 * math.sin(frac * math.pi)
                progress = 0.35 + (frac * 0.30) + var
            elif t <= t_s4_end:
                # Stage 4: Turn 2 West Semicircle (0.65 -> 0.85)
                frac = (t - t_s3_end) / (t_s4_end - t_s3_end)
                var = (f_turn2 - 0.5) * 0.025 * math.sin(frac * math.pi)
                progress = 0.65 + (frac * 0.20) + var
            else:
                # Stage 5: Home Stretch Sprint & Photo Finish (0.85 -> 1.00)
                frac = (t - t_s4_end) / max(0.001, (t_s5_end - t_s4_end))
                # Final finish margin: winner crosses at 1.00, trailing ranks finish separated by a nose
                trailing_gap = rank * 0.012
                target_finish = 1.00 - trailing_gap
                var = (f_stamina - 0.5) * 0.015 * math.sin(frac * math.pi)
                progress = 0.85 + (frac * (target_finish - 0.85)) + var

            progress = max(0.0, min(1.0, progress))
            x, y, heading = get_lane_point(slot, progress)

            telemetry[b_id].append({
                "t": round(t, 2),
                "x": round(x, 1),
                "y": round(y, 1),
                "angle": round(heading, 3),
                "progress": round(progress, 4)
            })

    # Winner details
    winner_id = sorted_racers[0][0]
    winner_bison = next((b for b in lineup if (b.get("id") or f"bison_{b.get('slot')}") == winner_id), None)
    telemetry["_winner"] = {
        "id": winner_id,
        "slot": winner_bison.get("slot", 1) if winner_bison else 1,
        "name": winner_bison.get("name", "Winner") if winner_bison else "Winner",
        "color": winner_bison.get("color", "#ffd700") if winner_bison else "#ffd700",
        "jockey_name": winner_bison.get("jockey_name", "Rider") if winner_bison else "Rider"
    }

    return telemetry
