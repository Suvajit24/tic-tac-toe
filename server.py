"""
server.py
Flask + Flask-SocketIO backend for Tic-Tac-Toe multiplayer rooms.
"""

from flask import Flask, send_from_directory, request
from flask_socketio import SocketIO, join_room, leave_room, emit
import uuid

app = Flask(__name__, static_folder="static", static_url_path="/")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

# In-memory store of games
games = {}

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

def new_game_state():
    return {"board": [""] * 9, "turn": "X", "players": {}, "status": "waiting", "winner": None}

@socketio.on("create_game")
def on_create_game(data):
    room_id = str(uuid.uuid4())[:8]
    games[room_id] = new_game_state()
    sid = request.sid
    games[room_id]["players"][sid] = "X"
    join_room(room_id)
    games[room_id]["status"] = "waiting"
    emit("game_created", {"room": room_id, "symbol": "X", "state": games[room_id]}, room=sid)

@socketio.on("join_game")
def on_join_game(data):
    room_id = data.get("room")
    sid = request.sid
    if room_id not in games:
        emit("error", {"message": "Room not found."}, room=sid)
        return
    game = games[room_id]
    if len(game["players"]) >= 2:
        emit("error", {"message": "Room full."}, room=sid)
        return
    game["players"][sid] = "O"
    join_room(room_id)
    game["status"] = "playing"
    emit("player_joined", {"room": room_id, "symbol": "O", "state": game}, room=room_id)

@socketio.on("make_move")
def on_make_move(data):
    room_id = data.get("room")
    idx = data.get("index")
    sid = request.sid
    if room_id not in games:
        emit("error", {"message": "Room not found."}, room=sid)
        return

    game = games[room_id]
    if game["status"] != "playing":
        emit("error", {"message": "Game not active."}, room=sid)
        return

    symbol = game["players"].get(sid)
    if symbol is None:
        emit("error", {"message": "You are not part of this game."}, room=sid)
        return

    if game["turn"] != symbol:
        emit("error", {"message": "Not your turn."}, room=sid)
        return

    if not (0 <= idx < 9) or game["board"][idx] != "":
        emit("error", {"message": "Invalid move."}, room=sid)
        return

    game["board"][idx] = symbol
    winner = check_winner(game["board"])
    if winner:
        game["status"] = "done"
        game["winner"] = winner
    elif all(cell != "" for cell in game["board"]):
        game["status"] = "done"
        game["winner"] = "draw"
    else:
        game["turn"] = "O" if game["turn"] == "X" else "X"
    emit("update_state", {"state": game}, room=room_id)

@socketio.on("restart_game")
def on_restart(data):
    room_id = data.get("room")
    if room_id not in games:
        return
    game = games[room_id]
    sids = list(game["players"].keys())
    new_state = new_game_state()
    new_state["players"] = {sids[0]: "X"}
    if len(sids) > 1:
        new_state["players"][sids[1]] = "O"
        new_state["status"] = "playing"
    games[room_id] = new_state
    emit("update_state", {"state": new_state}, room=room_id)

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    to_delete = []
    for room_id, game in list(games.items()):
        if sid in game["players"]:
            del game["players"][sid]
            emit("update_state", {"state": game}, room=room_id)
            if len(game["players"]) == 0:
                to_delete.append(room_id)
            else:
                game["status"] = "waiting"
    for r in to_delete:
        del games[r]

def check_winner(b):
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a,bidx,c in wins:
        if b[a] and b[a] == b[bidx] == b[c]:
            return b[a]
    return None

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
