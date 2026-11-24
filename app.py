import os
import random
import string
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-in-production")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Prototype storage: rooms live in memory and reset when the server restarts.
rooms = {}
sid_to_room = {}

BOARD_SIZE = 30
MIN_PLAYERS = 3
MAX_PLAYERS = 6
STARTING_POINTS = 100


def make_code():
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if code not in rooms:
            return code


def public_state(room):
    players = []
    for p in room["players"].values():
        players.append({
            "id": p["id"],
            "name": p["name"],
            "score": p["score"],
            "position": p["position"],
            "eliminated": p["eliminated"],
            "has_immunity": p["has_immunity"],
            "is_host": p["id"] == room["host_id"],
        })
    return {
        "code": room["code"],
        "status": room["status"],
        "players": players,
        "turn_order": room["turn_order"],
        "current_turn": room["current_turn"],
        "message": room["message"],
        "winner": room.get("winner"),
    }


def send_state(code):
    room = rooms.get(code)
    if room:
        socketio.emit("state", public_state(room), to=code)
        for sid, player_id in room["sid_to_player"].items():
            player = room["players"].get(player_id)
            if player:
                socketio.emit("private_state", {
                    "my_mine": player.get("mine"),
                    "my_id": player_id,
                    "my_immunity": player["has_immunity"],
                }, to=sid)


def current_player(room):
    if not room["turn_order"]:
        return None
    if room["current_turn"] >= len(room["turn_order"]):
        room["current_turn"] = 0
    pid = room["turn_order"][room["current_turn"]]
    return room["players"].get(pid)


def next_turn(room, previous_player_id):
    if not room["turn_order"]:
        return
    old_order = list(room["turn_order"])
    active = [pid for pid in old_order
              if pid in room["players"] and not room["players"][pid]["eliminated"]]
    room["turn_order"] = active
    if not active:
        room["current_turn"] = 0
        return

    # Pick the first still-active player after the player whose turn just ended.
    try:
        old_index = old_order.index(previous_player_id)
    except ValueError:
        old_index = -1
    next_id = None
    for offset in range(1, len(old_order) + 1):
        candidate = old_order[(old_index + offset) % len(old_order)]
        if candidate in active:
            next_id = candidate
            break
    room["current_turn"] = active.index(next_id) if next_id else 0


def draw_new_mine(room, player_id):
    held = {p["mine"] for pid, p in room["players"].items()
            if pid != player_id and p.get("mine") is not None}
    pool = [n for n in range(1, BOARD_SIZE + 1) if n not in held]
    room["players"][player_id]["mine"] = random.choice(pool)


def apply_move(room, player, signed_steps):
    old_position = player["position"]
    player["position"] = (old_position + signed_steps) % BOARD_SIZE
    landed = player["position"] + 1  # board labels are 1..30
    room["message"] = f'{player["name"]} 移动到第 {landed} 格。'

    # A player's own mine has no effect.
    target = next((p for pid, p in room["players"].items()
                  if pid != player["id"] and p.get("mine") == landed
                  and not p["eliminated"]), None)

    if target:
        if player["has_immunity"]:
            player["has_immunity"] = False
            room["message"] += f' 触发了 {target["name"]} 的暗雷，但免死金牌生效，没有发生积分转移。'
        else:
            amount = target["mine"]
            player["score"] -= amount
            target["score"] += amount
            room["message"] += f' 触发了 {target["name"]} 的暗雷，转移 {amount} 分。'
            # Redraw only after settlement; the old mine returns to the pool.
            draw_new_mine(room, target["id"])
            if player["score"] <= 0:
                player["eliminated"] = True
                room["message"] += f' {player["name"]} 积分归零或为负，淘汰。'

    return landed


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("create_room")
def create_room(data):
    name = (data.get("name") or "").strip()[:18]
    if not name:
        emit("error_message", "请先输入昵称。")
        return
    code = make_code()
    pid = request.sid
    room = {
        "code": code,
        "host_id": pid,
        "players": {
            pid: {
                "id": pid, "name": name, "score": STARTING_POINTS,
                "position": 0, "mine": None, "has_immunity": False,
                "eliminated": False,
            }
        },
        "sid_to_player": {request.sid: pid},
        "status": "waiting",
        "turn_order": [],
        "current_turn": 0,
        "message": "房间已创建，等待其他玩家加入。",
        "winner": None,
    }
    rooms[code] = room
    sid_to_room[request.sid] = code
    join_room(code)
    emit("room_joined", {"code": code, "player_id": pid})
    send_state(code)


@socketio.on("join_room")
def join_game(data):
    name = (data.get("name") or "").strip()[:18]
    code = (data.get("code") or "").strip().upper()
    room = rooms.get(code)
    if not name:
        emit("error_message", "请先输入昵称。")
        return
    if not room:
        emit("error_message", "找不到这个房间，请检查房间号码。")
        return
    if room["status"] != "waiting":
        emit("error_message", "游戏已经开始，暂时不能加入。")
        return
    if len(room["players"]) >= MAX_PLAYERS:
        emit("error_message", "房间已满，最多 6 人。")
        return
    pid = request.sid
    room["players"][pid] = {
        "id": pid, "name": name, "score": STARTING_POINTS,
        "position": 0, "mine": None, "has_immunity": False,
        "eliminated": False,
    }
    room["sid_to_player"][request.sid] = pid
    sid_to_room[request.sid] = code
    join_room(code)
    emit("room_joined", {"code": code, "player_id": pid})
    room["message"] = f"{name} 加入了房间。"
    send_state(code)


@socketio.on("start_game")
def start_game():
    code = sid_to_room.get(request.sid)
    room = rooms.get(code)
    if not room:
        emit("error_message", "你不在任何房间里。")
        return
    if request.sid != room["host_id"]:
        emit("error_message", "只有房主可以开始游戏。")
        return
    count = len(room["players"])
    if count < MIN_PLAYERS:
        emit("error_message", "至少需要 3 名玩家才能开始。")
        return
    if room["status"] != "waiting":
        emit("error_message", "游戏已经开始。")
        return

    mine_numbers = random.sample(range(1, BOARD_SIZE + 1), count)
    for (pid, player), mine in zip(room["players"].items(), mine_numbers):
        player["score"] = STARTING_POINTS
        player["position"] = 0
        player["mine"] = mine
        player["has_immunity"] = False
        player["eliminated"] = False

    room["status"] = "playing"
    room["turn_order"] = list(room["players"].keys())
    room["current_turn"] = 0
    room["message"] = "游戏开始！请当前玩家掷骰子。"
    send_state(code)


@socketio.on("roll_turn")
def roll_turn():
    code = sid_to_room.get(request.sid)
    room = rooms.get(code)
    if not room or room["status"] != "playing":
        emit("error_message", "游戏尚未开始。")
        return
    player = room["players"].get(request.sid)
    active = current_player(room)
    if not player or not active or active["id"] != request.sid:
        emit("error_message", "还没轮到你。")
        return
    if player["eliminated"]:
        emit("error_message", "你已被淘汰。")
        return

    die_a, die_b = random.randint(1, 6), random.randint(1, 6)
    sign = random.choice(["+", "-"])
    result = die_a + die_b if sign == "+" else die_a - die_b

    # Start-space safeguard as described by the game designer:
    # if a negative result occurs at the starting space, reroll once.
    if result < 0 and player["position"] == 0:
        retry_a, retry_b = random.randint(1, 6), random.randint(1, 6)
        retry_sign = random.choice(["+", "-"])
        retry_result = retry_a + retry_b if retry_sign == "+" else retry_a - retry_b
        if retry_result < 0:
            player["score"] -= 5
            result = 1
            room["message"] = (
                f'{player["name"]} 首次结果为负数，在起点重掷后仍为负数：扣除 5 分并前进 1 格。'
            )
        else:
            die_a, die_b, sign, result = retry_a, retry_b, retry_sign, retry_result
            room["message"] = f'{player["name"]} 在起点重掷，结果为 {die_a} {sign} {die_b} = {result}。'

    if result == 0:
        room["message"] = f'{player["name"]} 掷出 {die_a} {sign} {die_b} = 0，停留原地。'
    else:
        apply_move(room, player, result)

    if player["score"] <= 0:
        player["eliminated"] = True
        room["message"] += f' {player["name"]} 积分归零或为负，淘汰。'

    # A complete turn is settled before the next player acts.
    next_turn(room, player["id"])
    send_state(code)


@socketio.on("disconnect")
def on_disconnect():
    code = sid_to_room.pop(request.sid, None)
    if not code or code not in rooms:
        return
    room = rooms[code]
    pid = room["sid_to_player"].pop(request.sid, None)
    if pid and pid in room["players"]:
        # Keep the player record in the room for this prototype; mark offline.
        room["players"][pid]["offline"] = True
        room["message"] = f'{room["players"][pid]["name"]} 暂时断线。'
    send_state(code)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
