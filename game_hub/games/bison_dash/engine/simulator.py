import random
import math

STAGE_DURATIONS = {
    1: 7.0,
    2: 8.0,
    3: 7.0,
    4: 8.0
}

def roll_d20(): return random.randint(1, 20)
def roll_d1000(): return random.randint(1, 1000)
def roll_d6(): return random.randint(1, 6)
def roll_d100(): return random.randint(1, 100)

def simulate_race(lineup: list) -> dict:
    scores = {}
    for bison in lineup:
        # Fallbacks to prevent key errors if stats are somehow missing
        stats = bison.get('stats', {
            'jockey_reaction': 10,
            'bison_speed': 50,
            'bison_cornering': 5,
            'bison_stamina': 50
        })
        score1 = roll_d20() + stats['jockey_reaction']
        score2 = roll_d1000() + stats['bison_speed']
        score3 = roll_d6() + stats['bison_cornering']
        score4 = roll_d100() + stats['bison_stamina']

        total_score = score1 + score2 + score3 + score4
        scores[bison['id']] = total_score

    unique_scores = set(scores.values())
    while len(unique_scores) < len(lineup):
        for b_id1 in scores:
            for b_id2 in scores:
                if b_id1 != b_id2 and scores[b_id1] == scores[b_id2]:
                    r1 = roll_d6()
                    r2 = roll_d6()
                    if r1 > r2:
                        scores[b_id1] += 1
                    elif r2 > r1:
                        scores[b_id2] += 1
        unique_scores = set(scores.values())

    return _generate_telemetry(lineup, scores)

def _generate_telemetry(lineup: list, scores: dict) -> dict:
    # Proper Oval Track (Counter-Clockwise)
    # Start/Bottom Straight -> Turn 1 (Right Side) -> Top Straight -> Turn 2 (Left Side) -> Bottom Straight Finish
    waypoints = [
        {"t": 0.0, "pos": (960, 900)},    # Start line
        {"t": 3.75, "pos": (1520, 900)},  # Start of Turn 1
        {"t": 7.5, "pos": (1720, 700)},   # Turn 1 Apex 1
        {"t": 11.25, "pos": (1720, 500)}, # Turn 1 Apex 2
        {"t": 15.0, "pos": (1520, 300)},  # Start of Back Straight
        {"t": 18.75, "pos": (400, 300)},  # Start of Turn 2
        {"t": 22.5, "pos": (200, 500)},   # Turn 2 Apex 1
        {"t": 26.25, "pos": (200, 700)},  # Turn 2 Apex 2
        {"t": 28.125, "pos": (400, 900)}, # Start of Home Stretch
        {"t": 30.0, "pos": (960, 900)}    # Finish line
    ]

    sorted_bison = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ranks = {b_id: rank for rank, (b_id, score) in enumerate(sorted_bison)}

    telemetry = {}
    fps = 2

    for bison in lineup:
        b_id = bison['id']
        bison_rank = ranks[b_id]
        finish_offset_px = bison_rank * 40
        slot_offset_y = (bison['slot'] - 3.5) * 15
        slot_offset_x = (bison['slot'] - 3.5) * 20

        telemetry[b_id] = []

        for t_step in range(0, 30 * fps + 1):
            t = t_step / fps

            for i in range(len(waypoints) - 1):
                w1 = waypoints[i]
                w2 = waypoints[i+1]
                if w1["t"] <= t <= w2["t"]:
                    progress = (t - w1["t"]) / (w2["t"] - w1["t"])
                    random_jitter = math.sin(t * 2 + bison['slot']) * 10

                    if t == 30.0:
                        dx = w1["pos"][0] - w2["pos"][0]
                        dy = w1["pos"][1] - w2["pos"][1]
                        dist = math.hypot(dx, dy)
                        if dist != 0:
                            nx, ny = dx/dist, dy/dist
                        else:
                            nx, ny = 1, 0

                        x = w2["pos"][0] + nx * finish_offset_px
                        y = w2["pos"][1] + ny * finish_offset_px
                    else:
                        x = w1["pos"][0] + (w2["pos"][0] - w1["pos"][0]) * progress
                        y = w1["pos"][1] + (w2["pos"][1] - w1["pos"][1]) * progress

                        speed_bonus_px = ((len(lineup) - bison_rank) * 15) * math.sin(progress * math.pi)

                        dx = w2["pos"][0] - w1["pos"][0]
                        dy = w2["pos"][1] - w1["pos"][1]
                        dist = math.hypot(dx, dy)
                        if dist != 0:
                            x += (dx/dist) * speed_bonus_px
                            y += (dy/dist) * speed_bonus_px

                    x += slot_offset_x
                    y += slot_offset_y + random_jitter

                    telemetry[b_id].append({"t": t, "x": round(x), "y": round(y)})
                    break

    return telemetry
