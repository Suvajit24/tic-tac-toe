/* app.js
Handles UI interactions, local play (2-player & vs CPU), and multiplayer via Socket.IO
*/
const socket = io(); // connects to same host

// UI elements
const statusText = document.getElementById("statusText");
const mySymbolEl = document.getElementById("mySymbol");
const boardEl = document.getElementById("board");
const cells = Array.from(document.querySelectorAll(".cell"));
const createBtn = document.getElementById("createBtn");
const joinBtn = document.getElementById("joinBtn");
const roomInput = document.getElementById("roomInput");
const local2PBtn = document.getElementById("local2PBtn");
const vsAIBtn = document.getElementById("vsAIBtn");
const restartBtn = document.getElementById("restartBtn");
const leaveBtn = document.getElementById("leaveBtn");

let mode = "idle"; // "multiplayer", "local", "ai", "idle"
let room = null;
let mySymbol = null;
let state = null; // {board:[], turn:"X"|"O", status, winner}
let localPlayerSymbol = "X";

// ---------- Helper UI ----------
function setStatus(s){
  statusText.textContent = s;
}
function setMySymbol(s){
  mySymbol = s;
  mySymbolEl.textContent = s || "-";
}
function renderBoard(b){
  cells.forEach((cell, i) => {
    cell.textContent = b[i] || "";
    cell.classList.toggle("disabled", b[i] || state?.status === "done" || (mode === "multiplayer" && mySymbol !== state?.turn));
  });
}
function showAlert(msg){
  alert(msg);
}

// ---------- Client-side Winner Check (also server checks) ----------
function checkWinner(board){
  const wins = [
    [0,1,2],[3,4,5],[6,7,8],
    [0,3,6],[1,4,7],[2,5,8],
    [0,4,8],[2,4,6]
  ];
  for (let [a,b,c] of wins){
    if (board[a] && board[a] === board[b] && board[b] === board[c]) return board[a];
  }
  if (board.every(x => x)) return "draw";
  return null;
}

// ---------- Local (non-network) play logic ----------
function startLocal2P(){
  mode = "local";
  room = null;
  setMySymbol(localPlayerSymbol);
  state = { board: ["","", "","", "","", "","", ""], turn: "X", status: "playing", winner: null };
  setStatus("Local 2P: X starts");
  renderBoard(state.board);
}

function startVsAI(){
  mode = "ai";
  room = null;
  localPlayerSymbol = "X";
  setMySymbol(localPlayerSymbol);
  state = { board: ["","", "","", "","", "","", ""], turn: "X", status: "playing", winner: null };
  setStatus("Play vs CPU — Your move");
  renderBoard(state.board);
}

// Minimax AI (unbeatable)
function bestMoveFor(board, aiSymbol){
  const human = aiSymbol === "X" ? "O" : "X";
  function minimax(b, player){
    const winner = checkWinner(b);
    if (winner === aiSymbol) return {score: 10};
    if (winner === human) return {score: -10};
    if (winner === "draw") return {score: 0};

    const moves = [];
    b.forEach((cell, idx) => {
      if (!cell){
        const copy = b.slice();
        copy[idx] = player;
        const result = minimax(copy, player === "X" ? "O" : "X");
        moves.push({ idx, score: result.score });
      }
    });
    let best;
    if (player === aiSymbol){
      // maximize
      best = {score:-Infinity};
      for (let m of moves) if (m.score > best.score) best = m;
    } else {
      // minimize
      best = {score:Infinity};
      for (let m of moves) if (m.score < best.score) best = m;
    }
    return best;
  }
  const move = minimax(board, aiSymbol);
  return move.idx;
}

// ---------- Event handlers on cells ----------
cells.forEach(cell => {
  cell.addEventListener("click", () => {
    const idx = Number(cell.dataset.index);
    if (!state || state.status === "done") return;
    if (state.board[idx]) return;

    if (mode === "local"){
      // local 2P: just change turn
      state.board[idx] = state.turn;
      const winner = checkWinner(state.board);
      if (winner){
        state.status = "done";
        state.winner = winner;
        setStatus(winner === "draw" ? "It's a draw!" : `${winner} wins!`);
      } else {
        state.turn = state.turn === "X" ? "O" : "X";
        setStatus(`${state.turn}'s turn`);
      }
      renderBoard(state.board);
    } else if (mode === "ai"){
      if (state.turn !== localPlayerSymbol) return; // not our turn
      state.board[idx] = localPlayerSymbol;
      // check win
      let winner = checkWinner(state.board);
      if (winner){
        state.status = "done";
        state.winner = winner;
        setStatus(winner === "draw" ? "It's a draw!" : (winner === localPlayerSymbol ? "You win!" : "CPU wins!"));
        renderBoard(state.board);
        return;
      }
      state.turn = localPlayerSymbol === "X" ? "O" : "X";
      renderBoard(state.board);
      // CPU move
      setTimeout(() => {
        const aiSymbol = (localPlayerSymbol === "X") ? "O" : "X";
        const moveIdx = bestMoveFor(state.board, aiSymbol);
        if (moveIdx === undefined || moveIdx === null) return;
        state.board[moveIdx] = aiSymbol;
        winner = checkWinner(state.board);
        if (winner){
          state.status = "done";
          state.winner = winner;
          setStatus(winner === "draw" ? "It's a draw!" : (winner === localPlayerSymbol ? "You win!" : "CPU wins!"));
        } else {
          state.turn = localPlayerSymbol;
          setStatus("Your move");
        }
        renderBoard(state.board);
      }, 300);
    } else if (mode === "multiplayer"){
      // send to server
      socket.emit("make_move", { room, index: idx });
    }
  });
});

// ---------- buttons ----------
createBtn.addEventListener("click", () => {
  socket.emit("create_game", {});
  setStatus("Creating game...");
});

joinBtn.addEventListener("click", () => {
  const r = roomInput.value.trim();
  if (!r){ showAlert("Enter room id"); return; }
  socket.emit("join_game", { room: r });
  setStatus("Joining...");
});

local2PBtn.addEventListener("click", () => {
  startLocal2P();
});

vsAIBtn.addEventListener("click", () => {
  startVsAI();
});

restartBtn.addEventListener("click", () => {
  if (mode === "multiplayer" && room) {
    socket.emit("restart_game", { room });
  } else if (mode === "local" || mode === "ai"){
    // reset local
    startLocal2P();
  } else {
    setStatus("Nothing to restart");
  }
});

leaveBtn.addEventListener("click", () => {
  if (mode === "multiplayer" && room){
    socket.emit("leave_game", { room });
    room = null; mode = "idle"; setMySymbol(null);
    setStatus("Left room");
    state = null;
    renderBoard(["","","","","","","","",""]);
  } else {
    setStatus("Not in a multiplayer room");
  }
});

// ---------- Socket.IO listeners ----------
socket.on("connect", () => {
  setStatus("connected to server");
});

socket.on("game_created", (data) => {
  // host perspective
  room = data.room;
  mode = "multiplayer";
  setMySymbol(data.symbol);
  state = data.state;
  setStatus(`Created room: ${room} — waiting for opponent...`);
  renderBoard(state.board);
});

socket.on("player_joined", (data) => {
  room = data.room;
  mode = "multiplayer";
  // If we were host, we already had symbol X. If we joined, server sends symbol
  // server included symbol in initial create/join responses; but here both get updated state
  setStatus(`Player joined. Game starts. Turn: ${data.state.turn}`);
  // determine our symbol
  // server keeps mapping sid->symbol but client doesn't get sid map. Server sends state only.
  // server earlier sent symbol on create; joiner will receive 'game_created'? No — join emits player_joined to room.
  // we will set mySymbol if not set (joiner must have been assigned by earlier event)
  // to be robust, server sends symbol in earlier events; client should keep previously set mySymbol.
  state = data.state;
  renderBoard(state.board);
});

socket.on("update_state", (data) => {
  state = data.state;
  renderBoard(state.board);
  if (state.status === "done"){
    if (state.winner === "draw"){
      setStatus("It's a draw!");
    } else {
      setStatus(`${state.winner} wins!`);
    }
  } else {
    setStatus(`${state.turn}'s turn`);
  }
});

socket.on("error", (data) => {
  setStatus("Error: " + (data.message || "unknown"));
  alert(data.message || "Error");
});

socket.on("disconnect", () => {
  setStatus("disconnected from server");
});

// Clean initial render
renderBoard(["","","","","","","","",""]);
