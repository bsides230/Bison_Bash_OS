with open("game_hub/games/bison_dash/templates/projector.html", "r") as f:
    content = f.read()

# Make the track a proper oval and ensure leaderboard shows
old_waypoints = """        const waypoints = [
            {x: 960, y: 900},    // Start/Finish
            {x: 1600, y: 700},   // Turn 1
            {x: 1700, y: 400},   // Turn 2
            {x: 1500, y: 300},   // Back stretch start
            {x: 400, y: 300},    // Back stretch end
            {x: 200, y: 400},    // Turn 3
            {x: 300, y: 700},    // Turn 4
            {x: 960, y: 900}     // Start/Finish
        ];"""

new_waypoints = """        const waypoints = [
            {x: 960, y: 900},    // Start/Finish (Bottom middle)
            {x: 1500, y: 900},   // Bottom Right
            {x: 1700, y: 700},   // Turn 1
            {x: 1700, y: 500},   // Turn 2
            {x: 1500, y: 300},   // Top Right
            {x: 400, y: 300},    // Top Left
            {x: 200, y: 500},    // Turn 3
            {x: 200, y: 700},    // Turn 4
            {x: 400, y: 900},    // Bottom Left
            {x: 960, y: 900}     // Start/Finish
        ];"""

content = content.replace(old_waypoints, new_waypoints)

with open("game_hub/games/bison_dash/templates/projector.html", "w") as f:
    f.write(content)
