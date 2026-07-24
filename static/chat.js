(function () {
  const box = document.getElementById("chat-box");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const room = box.dataset.room;
  const me = box.dataset.me;

  box.scrollTop = box.scrollHeight;

  const socket = io();                       // 같은 오리진으로 연결 (세션 쿠키 인증)

  socket.on("connect", function () {
    socket.emit("join", { room: room });
  });

  socket.on("receive_message", function (data) {
    const div = document.createElement("div");
    div.className = "msg" + (data.sender === me ? " mine" : "");

    const u = document.createElement("span");
    u.className = "msg-user";
    u.textContent = data.sender;             // [보안] textContent → XSS 방어

    const t = document.createElement("span");
    t.className = "msg-text";
    t.textContent = data.content;            // [보안] innerHTML 금지, textContent 사용

    const tm = document.createElement("span");
    tm.className = "msg-time";
    tm.textContent = data.created_at;

    div.appendChild(u);
    div.appendChild(t);
    div.appendChild(tm);
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    const content = input.value.trim();
    if (!content) return;
    socket.emit("send_message", { room: room, content: content });
    input.value = "";
  });
})();
