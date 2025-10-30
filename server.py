"""
server.py
Flask + Flask-SocketIO backend for Tic-Tac-Toe multiplayer rooms.

Run: python server.py
"""
from flask import Flask, send_from_directory, request
from flask_socketio import SocketIO, join_room, leave_room, emit
import uuid
import eventlet

eventlet.monkey_patch()

app = Flask(__name__, static_folder="static", static_url_path="/")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# In-memory store of games
# Structure: games[room_id] = { "board": list(9, ""), "turn": "X" or "O", "players": {sid: symbol,...}, "status": "waiting/playing/done" }
games = {}

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

# Serve other static files (css/js)
@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

# Helper: new game state
def new_game_state():
    return {"board": [""] * 9, "turn": "X", "players": {}, "status": "waiting", "winner": None}

# Socket events
@socketio.on("create_game")
def on_create_game(data):
    """Client requests a new game; returns room id."""
    room_id = str(uuid.uuid4())[:8]  # short id
    games[room_id] = new_game_state()
    sid = request.sid
    # host immediately joins
    games[room_id]["players"][sid] = "X"
    join_room(room_id)
    games[room_id]["status"] = "waiting"
    emit("game_created", {"room": room_id, "symbol": "X", "state": games[room_id]}, room=sid)

@socketio.on("join_game")
def on_join_game(data):
    """Client requests to join existing room."""
    room_id = data.get("room")
    sid = request.sid
    if room_id not in games:
        emit("error", {"message": "Room not found."}, room=sid)
        return
    game = games[room_id]
    if len(game["players"]) >= 2:
        emit("error", {"message": "Room already full."}, room=sid)
        return
    # assign O to the joining player
    game["players"][sid] = "O"
    join_room(room_id)
    game["status"] = "playing"
    # notify both players about full start
    emit("player_joined", {"room": room_id, "symbol": "O", "state": game}, room=room_id)

@socketio.on("make_move")
def on_make_move(data):
    """
    data: { room: str, index: int }
    Validate turn, update board, check win/draw, broadcast updated state.
    """
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

    # Validate turn
    if game["turn"] != symbol:
        emit("error", {"message": "Not your turn."}, room=sid)
        return

    # Validate index
    if not (0 <= idx < 9) or game["board"][idx] != "":
        emit("error", {"message": "Invalid move."}, room=sid)
        return

    # Make move
    game["board"][idx] = symbol
    # Check for winner or draw
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
    game.update(new_game_state())
    # keep players mapping (they stay in room)
    # reassign players same symbols (re-add mapping)
    # but reset board and status
    # preserve existing players mapping: assume first joined mapping same symbol as before
    # To keep it simple: reassign present players to X and O deterministically
    sids = list(game["players"].keys())
    game["players"] = {}
    for i, s in enumerate(sids):
        game["players"][s] = "X" if i == 0 else "O"
    game["status"] = "playing" if len(sids) == 2 else "waiting"
    emit("update_state", {"state": game}, room=room_id)

@socketio.on("leave_game")
def on_leave(data):
    room_id = data.get("room")
    sid = request.sid
    if room_id in games:
        game = games[room_id]
        if sid in game["players"]:
            del game["players"][sid]
        leave_room(room_id)
        # if this empties the room, remove game
        if len(game["players"]) == 0:
            del games[room_id]
        else:
            game["status"] = "waiting"
            emit("update_state", {"state": game}, room=room_id)

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    # remove from any game they were in
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
    wins = [
        (0,1,2),(3,4,5),(6,7,8),
        (0,3,6),(1,4,7),(2,5,8),
        (0,4,8),(2,4,6)
    ]
    for a,bidx,c in wins:
        if b[a] and b[a] == b[bidx] == b[c]:
            return b[a]
    return None

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)

