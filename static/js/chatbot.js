/* =============================================
   SMARTINTERN — Smarty Chatbot Widget JS
   Place in: static/js/chatbot.js
   ============================================= */

document.addEventListener('DOMContentLoaded', function () {
  const bubble     = document.getElementById('smarty-bubble');
  const win        = document.getElementById('smarty-window');
  
  // Early exit: If the chatbot HTML isn't on this page, stop running the script to prevent errors.
  if (!bubble || !win) return;

  const msgs       = document.getElementById('smarty-messages');
  const input      = document.getElementById('smarty-input');
  const sendBtn    = document.getElementById('smarty-send');
  const typing     = document.getElementById('smarty-typing');
  const badge      = document.getElementById('smarty-badge');
  const welcome    = document.getElementById('smarty-welcome');
  const expandBtn  = document.getElementById('smarty-expand');
  const expandIcon = document.getElementById('smarty-expand-icon');
  const shrinkIcon = document.getElementById('smarty-shrink-icon');

  let history = [], isOpen = false, isFS = false, unread = 0;

  // ── Open / Close ─────────────────────────────────────────
  bubble.addEventListener('click', () => {
    isOpen = !isOpen;
    bubble.classList.toggle('is-open', isOpen);
    win.classList.toggle('is-open', isOpen);
    
    if (isOpen) {
      unread = 0;
      if (badge) {
        badge.classList.remove('show');
        badge.textContent = '';
      }
      setTimeout(() => { 
        if (input) input.focus(); 
      }, 280);
    }
  });

  // ── Expand / Shrink fullscreen ────────────────────────────
  if (expandBtn) {
    expandBtn.addEventListener('click', () => {
      isFS = !isFS;
      win.classList.toggle('is-fullscreen', isFS);
      expandIcon.style.display = isFS ? 'none'  : 'block';
      shrinkIcon.style.display = isFS ? 'block' : 'none';
      expandBtn.title = isFS ? 'Exit fullscreen' : 'Expand to fullscreen';
      setTimeout(() => input.focus(), 50);
    });
  }

  // ── Clear chat ────────────────────────────────────────────
  function clearChat() {
    history = [];
    [...msgs.children].forEach(el => {
      if (el.id !== 'smarty-welcome' && el.id !== 'smarty-typing') el.remove();
    });
    welcome.style.display = 'flex';
    typing.classList.remove('show');
  }
  
  const clearBtn = document.getElementById('smarty-clear');
  const sidebarClearBtn = document.getElementById('smarty-sidebar-clear');
  if (clearBtn) clearBtn.addEventListener('click', clearChat);
  if (sidebarClearBtn) sidebarClearBtn.addEventListener('click', clearChat);

  // ── Chips & sidebar prompts ───────────────────────────────
  document.querySelectorAll('.cb-chip, .cb-sidebar-prompt').forEach(el => {
    el.addEventListener('click', () => {
      input.value = el.textContent.trim();
      autoResize();
      send();
    });
  });

  // ── Input events ─────────────────────────────────────────
  if (input) {
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
    });
    input.addEventListener('input', autoResize);
  }
  
  if (sendBtn) {
    sendBtn.addEventListener('click', send);
  }

  // ── Send message ──────────────────────────────────────────
  async function send() {
    const text = input.value.trim();
    if (!text) return;

    welcome.style.display = 'none';
    addMsg('user', text);
    history.push({ role: 'user', content: text });

    input.value = '';
    input.style.height = 'auto';
    sendBtn.disabled = true;

    typing.classList.add('show');
    msgs.appendChild(typing);
    scrollBottom();

    try {
      const res  = await fetch('/api/chat', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ messages: history })
      });
      const data = await res.json();
      typing.classList.remove('show');

      const reply = data.reply || data.error || 'Something went wrong.';
      addMsg('bot', reply);
      history.push({ role: 'assistant', content: reply });

      if (!isOpen) {
        unread++;
        badge.textContent = unread > 9 ? '9+' : unread;
        badge.classList.add('show');
      }
    } catch {
      typing.classList.remove('show');
      addMsg('bot', '⚠️ Connection error. Please try again.');
    }

    sendBtn.disabled = false;
    input.focus();
  }

  // ── Add message bubble ────────────────────────────────────
  function addMsg(role, text) {
    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const row = document.createElement('div');
    row.className = `cb-msg ${role}`;
    row.innerHTML = `
      <div class="cb-msg-av">
        ${role === 'user'
          ? `<svg viewBox="0 0 24 24"><path d="M12 12a5 5 0 100-10A5 5 0 0012 12zm0 2c-5.33 0-8 2.67-8 4v1h16v-1c0-1.33-2.67-4-8-4z"/></svg>`
          : `<svg viewBox="0 0 24 24"><path d="M12 2C6.477 2 2 6.163 2 11.307c0 2.608 1.162 4.956 3.032 6.63L4 22l4.606-2.017A11.18 11.18 0 0012 20.614c5.523 0 10-4.163 10-9.307S17.523 2 12 2z"/></svg>`
        }
      </div>
      <div class="cb-msg-body">
        <div class="cb-bubble">${role === 'bot' ? format(text) : esc(text)}</div>
        <div class="cb-msg-time">${now}</div>
      </div>`;
    msgs.insertBefore(row, typing);
    scrollBottom();
  }

  // ── Format bot response (markdown-like → HTML) ────────────
  function format(text) {
    let s = esc(text);

    // Bold & italic
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*(.+?)\*/g,     '<em>$1</em>');

    // Inline code
    s = s.replace(/`([^`]+)`/g, '<code>$1</code>');

    const lines = s.split('\n');
    const out   = [];
    let inList  = false;

    for (const line of lines) {
      const l = line.trim();

      if (/^\d+[.)]\s/.test(l)) {
        if (!inList)          { out.push('<ol>');        inList = 'ol'; }
        else if (inList==='ul'){ out.push('</ul><ol>');  inList = 'ol'; }
        out.push('<li>' + l.replace(/^\d+[.)]\s/, '') + '</li>');

      } else if (/^[•\-\*]\s/.test(l)) {
        if (!inList)          { out.push('<ul>');        inList = 'ul'; }
        else if (inList==='ol'){ out.push('</ol><ul>');  inList = 'ul'; }
        out.push('<li>' + l.replace(/^[•\-\*]\s/, '') + '</li>');

      } else {
        if (inList === 'ol') { out.push('</ol>'); inList = false; }
        if (inList === 'ul') { out.push('</ul>'); inList = false; }

        if (l === '') {
          if (out.length && out[out.length - 1] !== '<br>') out.push('<br>');
        } else {
          out.push('<span>' + l + '</span><br>');
        }
      }
    }

    if (inList === 'ol') out.push('</ol>');
    if (inList === 'ul') out.push('</ul>');
    while (out.length && out[out.length - 1] === '<br>') out.pop();

    return out.join('');
  }

  // ── Helpers ───────────────────────────────────────────────
  function esc(s) {
    return s
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
  function scrollBottom() { msgs.scrollTop = msgs.scrollHeight; }
  function autoResize() {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 90) + 'px';
  }

});