const chatContainer = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const loadingIndicator = document.getElementById('loading-indicator');

let isVerified = false;
let currentEmployeeId = null;
let typingAbort = null;
let lastSender = null; // Để kiểm soát hiển thị avatar VIBA

// Tự động resize ô nhập
messageInput.addEventListener('input', () => {
  messageInput.style.height = 'auto';
  messageInput.style.height = `${messageInput.scrollHeight}px`;
});

// Enter để gửi
messageInput.addEventListener('keypress', function (event) {
  if (event.key === 'Enter' && !event.shiftKey && !messageInput.disabled) {
    event.preventDefault();
    handleSend();
  }
});

sendButton.addEventListener('click', () => {
  if (sendButton.classList.contains('stop')) {
    if (typeof typingAbort === 'function') typingAbort();
    stopTypingState();
  } else {
    handleSend();
  }
});

function typeEffect(element, text, callback) {
  let i = 0;
  const speed = 12;
  element.textContent = '';
  chatContainer.scrollTop = chatContainer.scrollHeight;
  let aborted = false;
  typingAbort = () => aborted = true;

  function typeCharacter() {
    if (aborted) {
      element.textContent = text;
      addTimestamp(element);
      if (callback) callback();
      return;
    }
    if (i < text.length) {
      element.textContent += text.charAt(i++);
      chatContainer.scrollTop = chatContainer.scrollHeight;
      setTimeout(typeCharacter, speed);
    } else {
      addTimestamp(element);
      if (callback) callback();
    }
  }

  typeCharacter();
}

function startTypingState() {
  sendButton.classList.add('stop');
  sendButton.title = 'Dừng trả lời';
  sendButton.innerHTML = '⏹';
}

function stopTypingState() {
  typingAbort = null;
  sendButton.classList.remove('stop');
  sendButton.title = 'Gửi câu hỏi';
  sendButton.innerHTML = '➤';
  enableInputForQuestions();
}

function addTimestamp(container) {
  const now = new Date();
  const timeString = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  const span = document.createElement('div');
  span.classList.add('timestamp');
  span.textContent = timeString;
  container.appendChild(span);
}

function addMessageToChat(text, sender, useTyping = false, callback) {
  const wrapper = document.createElement('div');
  wrapper.classList.add('message-wrapper', `${sender}-wrapper`);

  // Avatar VIBA nếu là AI và khác lần trước
  if (sender === 'ai') {
    if (lastSender !== 'ai') {
      const avatar = document.createElement('div');
      avatar.classList.add('avatar');
      wrapper.appendChild(avatar);
    } else {
      const spacer = document.createElement('div');
      spacer.style.width = '32px';
      wrapper.appendChild(spacer);
    }
  }

  const messageDiv = document.createElement('div');
  messageDiv.classList.add('message', `${sender}-message`);

  if (sender === 'ai' && useTyping) {
    startTypingState();
    typeEffect(messageDiv, text, () => {
      stopTypingState();
      if (callback) callback();
    });
  } else {
    messageDiv.textContent = text;
    addTimestamp(messageDiv);
    if (callback) callback();
  }

  wrapper.appendChild(messageDiv);
  chatContainer.appendChild(wrapper);
  chatContainer.scrollTop = chatContainer.scrollHeight;
  lastSender = sender;
}

function enableInputForQuestions() {
  messageInput.placeholder = 'Nhập câu hỏi của bạn...';
  messageInput.disabled = false;
  sendButton.disabled = false;
  sendButton.title = 'Gửi câu hỏi';
  sendButton.innerHTML = '➤';
  messageInput.focus();
}

function enableInputForRetryVerification() {
  messageInput.placeholder = 'Mã không đúng. Vui lòng nhập lại Mã cán bộ...';
  messageInput.disabled = false;
  sendButton.disabled = false;
  sendButton.title = 'Gửi Mã cán bộ';
  messageInput.focus();
}

function disableInput() {
  messageInput.disabled = true;
  sendButton.disabled = true;
  sendButton.title = 'Đang xử lý...';
}

async function handleSend() {
  const text = messageInput.value.trim();
  if (!text) return;

  addMessageToChat(text, 'user');
  messageInput.value = '';
  messageInput.style.height = 'auto';
  disableInput();

  loadingIndicator.style.display = 'block';

  if (!isVerified) {
    loadingIndicator.textContent = 'Đang xác thực Mã cán bộ...';
    try {
      const res = await fetch('/verify_employee', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ employee_id: text })
      });
      const data = await res.json();
      loadingIndicator.style.display = 'none';

      if (res.ok && data.status === 'success') {
        isVerified = true;
        currentEmployeeId = text;
        addMessageToChat(data.greeting, 'ai', true, () => {
          const files = data.file_list || [];
          if (files.length > 0) {
            let msg = "Tôi có thể hỗ trợ bạn trên cơ sở các văn bản sau:\n";
            files.forEach((f, i) => msg += `${i + 1}. ${f}\n`);
            msg += "Xin mời đặt câu hỏi.";
            addMessageToChat(msg.trim(), 'ai', true);
          } else {
            addMessageToChat("Bạn cần hỗ trợ gì tiếp theo?", 'ai', true);
          }
        });
      } else {
        addMessageToChat(data.message || "Xác thực thất bại.", 'ai', true, enableInputForRetryVerification);
      }
    } catch (e) {
      loadingIndicator.style.display = 'none';
      addMessageToChat("Lỗi kết nối xác thực. Vui lòng thử lại.", 'ai', true, enableInputForRetryVerification);
    }
  } else {
    loadingIndicator.textContent = 'VIBA đang trả lời...';
    try {
      const res = await fetch('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, employee_id: currentEmployeeId })
      });
      const data = await res.json();
      loadingIndicator.style.display = 'none';

      if (!res.ok || data.error) {
        throw new Error(data.error || `Lỗi HTTP ${res.status}`);
      }

      addMessageToChat(data.answer || "Xin lỗi, tôi chưa có câu trả lời phù hợp.", 'ai', true);
    } catch (e) {
      loadingIndicator.style.display = 'none';
      addMessageToChat(`Lỗi: ${e.message}`, 'ai', true);
    }
  }
}

function initializeChat() {
  const welcome = `Xin chào! Tôi là VIBA - Trợ lý ảo nội bộ BIDV Bắc Hải Dương.\nTôi có thể giúp bạn tra cứu văn bản và trả lời câu hỏi nghiệp vụ.\nVui lòng nhập Mã cán bộ để bắt đầu.`;
  addMessageToChat(welcome, 'ai', true, () => {
    messageInput.placeholder = 'Nhập Mã cán bộ...';
    messageInput.disabled = false;
    sendButton.disabled = false;
    sendButton.title = 'Gửi Mã cán bộ';
    messageInput.focus();
  });
}

document.addEventListener('DOMContentLoaded', initializeChat);
