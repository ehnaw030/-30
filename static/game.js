const socket = io();
const $ = (id) => document.getElementById(id);
let roomCode = null;
let myId = null;
let state = null;
let privateState = null;

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2600);
}
function enterRoom(data) {
  roomCode = data.code;
  myId = data.player_id;
  $("entry").classList.add("hidden");
  $("game").classList.remove("hidden");
  $("codeDisplay").textContent = roomCode;
}
$("createBtn").onclick = () => socket.emit("create_room", {name:$("playerName").value});
$("joinBtn").onclick = () => socket.emit("join_room", {name:$("playerName").value, code:$("roomCode").value});
$("startBtn").onclick = () => socket.emit("start_game");
$("rollBtn").onclick = () => socket.emit("roll_turn");

socket.on("room_joined", enterRoom);
socket.on("error_message", toast);
socket.on("private_state", data => {
  privateState = data;
  $("myMine").textContent = data.my_mine ?? "尚未分配";
  $("immunityInfo").textContent = data.my_immunity ? "你持有免死金牌" : "目前没有免死金牌";
});
socket.on("state", data => {
  state = data;
  $("codeDisplay").textContent = data.code;
  $("statusDisplay").textContent = data.status === "playing" ? "游戏进行中" : "等待玩家";
  $("gameMessage").textContent = data.message || "";
  $("startBtn").classList.toggle("hidden", !(data.status === "waiting" && myId === data.players.find(p=>p.id===myId)?.id && data.players.some(p=>p.is_host)));
  $("startBtn").disabled = data.players.length < 3;
  const active = data.players.find(p=>p.id === data.current_turn);
  // current_turn is an index into turn_order; find current player from order.
  const currentId = data.turn_order[data.current_turn];
  const current = data.players.find(p=>p.id===currentId);
  $("turnInfo").textContent = data.status !== "playing" ? `等待玩家加入（${data.players.length}/6）` :
    current ? `轮到：${current.name}${current.id===myId ? "（你）" : ""}` : "等待下一回合";
  $("rollBtn").disabled = !(data.status === "playing" && currentId === myId);
  $("players").innerHTML = "";
  data.players.forEach(p => {
    const row = document.createElement("div");
    row.className = "player" + (p.id===currentId && data.status==="playing" ? " current" : "") + (p.eliminated ? " out" : "");
    const name = document.createElement("div");
    name.className = "player-name";
    name.textContent = p.name + (p.is_host ? " · 房主" : "") + (p.eliminated ? " · 淘汰" : "");
    const meta = document.createElement("div");
    meta.className = "player-meta";
    meta.textContent = `${p.score} 分 · 第 ${p.position+1} 格`;
    row.append(name,meta);
    $("players").append(row);
  });
  $("board").innerHTML = "";
  for(let n=1;n<=30;n++){
    const cell = document.createElement("div");
    cell.className = "cell";
    const occupants = data.players.filter(p=>!p.eliminated && p.position===n-1).map(p=>p.name);
    if(occupants.length) cell.classList.add("occupied");
    const num = document.createElement("span"); num.textContent = n;
    const small = document.createElement("small"); small.textContent = occupants.join("、");
    cell.append(num,small);
    $("board").append(cell);
  }
});
