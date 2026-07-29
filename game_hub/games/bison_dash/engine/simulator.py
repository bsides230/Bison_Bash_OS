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

def simulate_race(lineup: list, duration: int = 90) -> dict:
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

    return _generate_telemetry(lineup, scores, duration)

def get_normal(p1, p2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    dist = math.hypot(dx, dy)
    if dist == 0:
        return (0, 0)
    # Right-hand normal since path is counter-clockwise, meaning right normal is 'outer'
    # Actually wait: counter-clockwise means right normal points inward?
    # Let's use (dy/dist, -dx/dist) for inward or (-dy/dist, dx/dist) for outward.
    return (dy/dist, -dx/dist)

def compute_lane_waypoints(base_waypoints, lane_index, lane_width=40):
    # Calculate offset per lane, centered around the base path
    # If lane_index is 1 to 6, let's map it to an offset
    # Let's say offset from center: (lane_index - 3.5) * lane_width
    offset = (lane_index - 3.5) * lane_width

    n_pts = len(base_waypoints)
    lane_path = []

    for i in range(n_pts):
        p_prev = base_waypoints[i-1]["pos"] if i > 0 else base_waypoints[-2]["pos"] # Wrap around for closed loop if needed, but start/end are same
        p_curr = base_waypoints[i]["pos"]
        p_next = base_waypoints[i+1]["pos"] if i < n_pts - 1 else base_waypoints[1]["pos"]

        n1 = get_normal(p_prev, p_curr)
        n2 = get_normal(p_curr, p_next)

        # Average normals for a smooth miter join
        nx = n1[0] + n2[0]
        ny = n1[1] + n2[1]

        # Normalize the average normal
        n_dist = math.hypot(nx, ny)
        if n_dist != 0:
            nx /= n_dist
            ny /= n_dist
        else:
            nx, ny = n1[0], n1[1]

        lane_path.append({
            "t": base_waypoints[i]["t"],
            "pos": (p_curr[0] + nx * offset, p_curr[1] + ny * offset)
        })

    # Ensure start and end perfectly match if they were exactly identical originally
    if base_waypoints[0]["pos"] == base_waypoints[-1]["pos"]:
        lane_path[-1]["pos"] = lane_path[0]["pos"]

    return lane_path

def _generate_telemetry(lineup: list, scores: dict, duration: int) -> dict:
    # Proper Oval Track (Counter-Clockwise)
    # Start/Bottom Straight -> Turn 1 (Right Side) -> Top Straight -> Turn 2 (Left Side) -> Bottom Straight Finish
    base_waypoints = [
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

    # Scale times dynamically to match `duration`
    scale_factor = duration / 30.0
    for w in base_waypoints:
        w["t"] *= scale_factor

    sorted_bison = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ranks = {b_id: rank for rank, (b_id, score) in enumerate(sorted_bison)}

    telemetry = {}
    fps = 2

    for bison in lineup:
        b_id = bison['id']
        bison_rank = ranks[b_id]
        finish_offset_px = bison_rank * 40

        lane_waypoints = compute_lane_waypoints(base_waypoints, bison['slot'], lane_width=40)

        telemetry[b_id] = []

        for t_step in range(0, int(duration * fps) + 1):
            t = t_step / fps

            for i in range(len(lane_waypoints) - 1):
                w1 = lane_waypoints[i]
                w2 = lane_waypoints[i+1]
                if w1["t"] <= t <= w2["t"]:
                    progress = (t - w1["t"]) / (w2["t"] - w1["t"])

                    if t == duration:
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

                    telemetry[b_id].append({"t": t, "x": round(x), "y": round(y)})
                    break

    return telemetry
