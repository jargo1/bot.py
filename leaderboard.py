import json

# Funktsioonid edetabeli haldamiseks
def load_leaderboard():
    try:
        with open("leaderboard.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_leaderboard(leaderboard):
    with open("leaderboard.json", "w") as file:
        json.dump(leaderboard, file, indent=4)

def update_leaderboard(player_name, score):
    leaderboard = load_leaderboard()
    leaderboard[player_name] = score
    save_leaderboard(leaderboard)

def get_leaderboard():
    leaderboard = load_leaderboard()
    sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1], reverse=True)
    return sorted_leaderboard
