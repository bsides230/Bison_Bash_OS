import random
import math

# Fixed path lengths representing the isometric oval
# Total = 30 seconds
STAGE_DURATIONS = {
    1: 7.0,  # Launch & Back Straightaway (0 - 7s)
    2: 8.0,  # Curved Corner 1 (7 - 15s)
    3: 7.0,  # Home Stretch (15 - 22s)
    4: 8.0   # Finish Line Approach (22 - 30s)
}

def roll_d20(): return random.randint(1, 20)
def roll_d1000(): return random.randint(1, 1000)
def roll_d6(): return random.randint(1, 6)
def roll_d100(): return random.randint(1, 100)

def simulate_race(lineup: list) -> dict:
    """
    Calculates deterministic race scores for the 6 bison and maps them to a dense telemetry array.
    Outputs: { "bison_id": [{"t": 0.0, "x": 100, "y": 200}, ...] }
    """
    scores = {}
    for bison in lineup:
        stats = bison['stats']
        # Stage 1: Launch (D20 + Jockey)
        score1 = roll_d20() + stats['jockey_reaction']

        # Stage 2: Back Straightaway (D1000 + Speed)
        score2 = roll_d1000() + stats['bison_speed']

        # Stage 3: Curved Corners (D6 + Cornering)
        score3 = roll_d6() + stats['bison_cornering']

        # Stage 4: Home Stretch (D100 + Stamina)
        score4 = roll_d100() + stats['bison_stamina']

        total_score = score1 + score2 + score3 + score4
        scores[bison['id']] = total_score

    # Handle ties with D6 roll-offs
    unique_scores = set(scores.values())
    while len(unique_scores) < len(lineup):
        # Tie detected
        for b_id1 in scores:
            for b_id2 in scores:
                if b_id1 != b_id2 and scores[b_id1] == scores[b_id2]:
                    # Roll-off
                    r1 = roll_d6()
                    r2 = roll_d6()
                    if r1 > r2:
                        scores[b_id1] += 1
                    elif r2 > r1:
                        scores[b_id2] += 1
        unique_scores = set(scores.values())

    # Map to telemetry
    return _generate_telemetry(lineup, scores)

def _generate_telemetry(lineup: list, scores: dict) -> dict:
    """
    Maps 30-second deterministic telemetry for a 1920x1080 canvas.
    Lower score = finishes slightly behind at exactly 30s.
    """
    # Track Waypoints (Diamond Oval)
    # Start (bottom center): (960, 900)
    # Top Left (Corner 1 Start): (400, 400)
    # Top Right (Corner 1 End / Home Stretch Start): (1520, 400)
    # Bottom Right (Home stretch end): (1300, 750)
    # Finish Line (Start point): (960, 900)

    # Note: the brief says:
    # Seconds 0-7: Move up the Back Straightaway (bottom-center to top-left).
    # Seconds 7-15: Corner 1 (top-left to top-right).
    # Seconds 15-22: Home Stretch (top-right to bottom-right).
    # Seconds 22-30: Finish Line (bottom-right to bottom-center).

    waypoints = [
        {"t": 0.0, "pos": (960, 900)},
        {"t": 7.0, "pos": (400, 400)},
        {"t": 15.0, "pos": (1520, 400)},
        {"t": 22.0, "pos": (1300, 750)},
        {"t": 30.0, "pos": (960, 900)}
    ]

    # Calculate rank based on score to stagger finish line
    sorted_bison = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ranks = {b_id: rank for rank, (b_id, score) in enumerate(sorted_bison)}

    telemetry = {}
    fps = 2  # 2 frames per second (every 0.5s) for lightweight dense array

    for bison in lineup:
        b_id = bison['id']
        bison_rank = ranks[b_id]
        # Calculate staggering based on rank
        # 1st place finishes exactly on finish line, others finish slightly behind on the track
        # Let's say each rank is spaced 40 pixels behind the one in front at the finish.
        finish_offset_px = bison_rank * 40
        slot_offset_y = (bison['slot'] - 3.5) * 15 # Spread them slightly vertically/horizontally
        slot_offset_x = (bison['slot'] - 3.5) * 20

        telemetry[b_id] = []

        for t_step in range(0, 30 * fps + 1):
            t = t_step / fps

            # Find current stage segment
            for i in range(len(waypoints) - 1):
                w1 = waypoints[i]
                w2 = waypoints[i+1]
                if w1["t"] <= t <= w2["t"]:
                    # Progress between 0 and 1
                    progress = (t - w1["t"]) / (w2["t"] - w1["t"])

                    # Apply elastic effect - rubber banding based on score
                    # For visual interest, random micro-variations that resolve by the end
                    random_jitter = math.sin(t * 2 + bison['slot']) * 10

                    if t == 30.0:
                        # Final position deterministic logic
                        # Stagger them backwards along the final segment vector
                        dx = w1["pos"][0] - w2["pos"][0]
                        dy = w1["pos"][1] - w2["pos"][1]
                        dist = math.hypot(dx, dy)
                        nx, ny = dx/dist, dy/dist

                        x = w2["pos"][0] + nx * finish_offset_px
                        y = w2["pos"][1] + ny * finish_offset_px
                    else:
                        x = w1["pos"][0] + (w2["pos"][0] - w1["pos"][0]) * progress
                        y = w1["pos"][1] + (w2["pos"][1] - w1["pos"][1]) * progress

                        # Add rank-based speed variance early on that evens out
                        # so higher scores are slightly ahead during the race
                        speed_bonus_px = ((len(lineup) - bison_rank) * 15) * math.sin(progress * math.pi)

                        dx = w2["pos"][0] - w1["pos"][0]
                        dy = w2["pos"][1] - w1["pos"][1]
                        dist = math.hypot(dx, dy)
                        if dist != 0:
                            x += (dx/dist) * speed_bonus_px
                            y += (dy/dist) * speed_bonus_px

                    # Apply lane separation
                    x += slot_offset_x
                    y += slot_offset_y + random_jitter

                    telemetry[b_id].append({"t": t, "x": round(x), "y": round(y)})
                    break

    return telemetry
