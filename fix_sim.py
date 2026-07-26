with open("game_hub/games/bison_dash/templates/projector.html", "r") as f:
    content = f.read()

# Make the simulator track match a perfect race track oval
old_waypoints = """        const waypoints = [
            {x: 960, y: 900},
            {x: 1600, y: 900},
            {x: 1700, y: 700},
            {x: 1700, y: 500},
            {x: 1600, y: 300},
            {x: 320, y: 300},
            {x: 220, y: 500},
            {x: 220, y: 700},
            {x: 320, y: 900},
            {x: 960, y: 900}
        ];"""

new_waypoints = """        const waypoints = [
            {x: 960, y: 850},
            {x: 1550, y: 850},
            {x: 1650, y: 750},
            {x: 1700, y: 600},
            {x: 1650, y: 450},
            {x: 1550, y: 350},
            {x: 370, y: 350},
            {x: 270, y: 450},
            {x: 220, y: 600},
            {x: 270, y: 750},
            {x: 370, y: 850},
            {x: 960, y: 850}
        ];"""

content = content.replace(old_waypoints, new_waypoints)

# Also fix the start line positioning to be in the middle of the bottom straight
old_sl = """            // Draw Start/Finish line
            ctx.strokeStyle = '#ff0';
            ctx.lineWidth = 10;
            ctx.beginPath();
            ctx.moveTo(850, 900);
            ctx.lineTo(1070, 900);
            ctx.stroke();"""

new_sl = """            // Draw Start/Finish line
            ctx.strokeStyle = '#ff0';
            ctx.lineWidth = 10;
            ctx.beginPath();
            ctx.moveTo(960, 775);
            ctx.lineTo(960, 925);
            ctx.stroke();"""

content = content.replace(old_sl, new_sl)


with open("game_hub/games/bison_dash/templates/projector.html", "w") as f:
    f.write(content)

with open("game_hub/games/bison_dash/engine/simulator.py", "r") as f:
    content = f.read()

# Make the simulator track match
old_waypoints = """TRACK_WAYPOINTS = [
    (960, 900),
    (1600, 900),
    (1700, 700),
    (1700, 500),
    (1600, 300),
    (320, 300),
    (220, 500),
    (220, 700),
    (320, 900),
    (960, 900)
]"""

new_waypoints = """TRACK_WAYPOINTS = [
    (960, 850),
    (1550, 850),
    (1650, 750),
    (1700, 600),
    (1650, 450),
    (1550, 350),
    (370, 350),
    (270, 450),
    (220, 600),
    (270, 750),
    (370, 850),
    (960, 850)
]"""

content = content.replace(old_waypoints, new_waypoints)

with open("game_hub/games/bison_dash/engine/simulator.py", "w") as f:
    f.write(content)
