// Import Vue 3 from CDN
const { createApp, ref, computed, watch, nextTick, onMounted } = Vue;

// API base - configurable via /config.js
const API = window.__TIANHENG_API_BASE__ || window.location.origin;

// Token management
function getToken() { return localStorage.getItem('tianheng_token'); }
function setToken(t) { localStorage.setItem('tianheng_token', t); }
function getUser() { try { return JSON.parse(localStorage.getItem('tianheng_user') || 'null'); } catch { return null; } }
function setUser(u) { localStorage.setItem('tianheng_user', JSON.stringify(u)); }
function clearAuth() { localStorage.removeItem('tianheng_token'); localStorage.removeItem('tianheng_user'); }

// Simple markdown renderer
function renderMarkdown(text) {
  if (!text) return '';
  let html = text
    // Headers
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^# (.+)$/gm, '<h1>$1</h1>')
    // Bold & italic
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    // Images
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1">')
    // Horizontal rules
    .replace(/^---$/gm, '<hr>')
    // Blockquotes
    .replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
    // Unordered lists
    .replace(/^[\*\-] (.+)$/gm, '<li>$1</li>')
    // Ordered lists
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    // Code blocks
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
    // Line breaks
    .replace(/\n\n/g, '</p><p>')
    .replace(/\n/g, '<br>');
  
  // Wrap consecutive <li> in <ul>
  html = html.replace(/((?:<li>.*?<\/li><br>?)+)/g, '<ul>$1</ul>');
  
  // Wrap in paragraphs if not already
  if (!html.startsWith('<h') && !html.startsWith('<pre') && !html.startsWith('<ul') && !html.startsWith('<blockquote') && !html.startsWith('<hr')) {
    html = '<p>' + html + '</p>';
  }
  
  // Clean <br> after block elements
  html = html.replace(/<\/(h[123]|pre|ul|blockquote|li)><br>/g, '</$1>');
  
  return html;
}

// App
const App = {
  setup() {
    const loading = ref(true);
    const loggedIn = ref(false);
    const user = ref(getUser());
    const loginForm = ref({ username: '', password: '' });
    const loginError = ref('');
    const logging = ref(false);
    const sidebarOpen = ref(false);
    const currentView = ref('chat');
    const question = ref('');
    const framework = ref('epic');
    const messages = ref([]);
    const thinking = ref(false);
    const chatSessions = ref([]);
    const currentSessionId = ref(null);
    
    // Check auth on load
    onMounted(async () => {
      const token = getToken();
      if (token) {
        try {
          const res = await fetch(`${API}/api/auth/check`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token })
          });
          const data = await res.json();
          if (data.valid) {
            loggedIn.value = true;
            user.value = data.user;
            setUser(data.user);
            loadSessions();
          } else {
            clearAuth();
          }
        } catch { clearAuth(); }
      }
      loading.value = false;
    });
    
    // Login
    async function doLogin() {
      if (!loginForm.value.username || !loginForm.value.password) {
        loginError.value = '请输入用户名和密码';
        return;
      }
      logging.value = true;
      loginError.value = '';
      try {
        const res = await fetch(`${API}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(loginForm.value)
        });
        const data = await res.json();
        if (data.success) {
          setToken(data.token);
          setUser(data.user);
          user.value = data.user;
          loggedIn.value = true;
          loadSessions();
        } else {
          loginError.value = data.error || '登录失败';
        }
      } catch (e) {
        loginError.value = '无法连接到服务器';
      }
      logging.value = false;
    }
    
    function doLogout() {
      clearAuth();
      loggedIn.value = false;
      user.value = null;
      messages.value = [];
      chatSessions.value = [];
    }
    
    // Chat
    function newChat() {
      currentView.value = 'chat';
      messages.value = [];
      currentSessionId.value = null;
      question.value = '';
    }
    
    function switchChat(s) {
      currentSessionId.value = s.id;
      currentView.value = 'chat';
      sidebarOpen.value = false;
      loadChatMessages(s.id);
    }

    async function loadChatMessages(sessionId) {
      try {
        messages.value = [];
        currentSessionId.value = sessionId;
        const res = await fetch(`${API}/api/qa/${sessionId}`);
        const data = await res.json();
        if (data.question) {
          messages.value = [
            { role: 'user', content: data.question, time: data.created_time || '' },
            { role: 'assistant', content: data.answer, time: data.created_time || '' }
          ];
        }
      } catch (e) { console.error(e); }
    }
    
    async function sendMessage() {
      if (!question.value.trim() || thinking.value) return;
      const q = question.value.trim();
      question.value = '';
      
      messages.value.push({
        role: 'user',
        content: q,
        time: new Date().toLocaleTimeString()
      });
      
      thinking.value = true;
      scrollToBottom();
      
      try {
        const res = await fetch(`${API}/api/qa/ask-stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q, framework: framework.value })
        });
        
        if (!res.ok) {
          messages.value.push({
            role: 'assistant',
            content: '抱歉，请求失败了，请稍后重试。',
            time: new Date().toLocaleTimeString()
          });
          thinking.value = false;
          scrollToBottom();
          return;
        }
        
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let fullContent = '';
        let fullReasoning = '';
        let answerChunk = { role: 'assistant', content: '', time: '' };
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const text = decoder.decode(value);
          const lines = text.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                
                if (data.type === 'content') {
                  fullContent += data.data;
                  // Update last message
                  if (messages.value.length > 0 && messages.value[messages.value.length - 1].role === 'assistant') {
                    messages.value[messages.value.length - 1].content = fullContent;
                  } else {
                    answerChunk = { role: 'assistant', content: fullContent, time: new Date().toLocaleTimeString() };
                    messages.value.push(answerChunk);
                  }
                  scrollToBottom();
                } else if (data.type === 'reasoning') {
                  fullReasoning += data.data;
                } else if (data.type === 'done') {
                  if (messages.value.length > 0 && messages.value[messages.value.length - 1].role === 'assistant') {
                    messages.value[messages.value.length - 1].time = new Date().toLocaleTimeString();
                  }
                  // Add to chat sessions
                  if (data.data && data.data.qa_id) {
                    currentSessionId.value = data.data.qa_id;
                    const title = q.length > 30 ? q.substring(0, 30) + '...' : q;
                    chatSessions.value.unshift({
                      id: data.data.qa_id,
                      title: title,
                      time: new Date().toLocaleString()
                    });
                    // Keep max 50
                    if (chatSessions.value.length > 50) chatSessions.value.pop();
                  }
                } else if (data.type === 'error') {
                  messages.value.push({
                    role: 'assistant',
                    content: '抱歉，处理问题时出错：' + data.data,
                    time: new Date().toLocaleTimeString()
                  });
                }
              } catch (e) { /* ignore parse errors */ }
            }
          }
        }
        
        // Ensure message is shown
        if (fullContent && !(messages.value.length > 0 && messages.value[messages.value.length - 1].role === 'assistant')) {
          messages.value.push({
            role: 'assistant',
            content: fullContent,
            time: new Date().toLocaleTimeString()
          });
        }
      } catch (e) {
        messages.value.push({
          role: 'assistant', 
          content: '抱歉，网络连接失败，请检查服务器是否正常运行。',
          time: new Date().toLocaleTimeString() 
        });
      }
      
      thinking.value = false;
      scrollToBottom();
    }
    
    function askSample(q) {
      question.value = q;
      sendMessage();
    }
    
    function scrollToBottom() {
      nextTick(() => {
        const container = document.querySelector('.messages-container');
        if (container) container.scrollTop = container.scrollHeight;
      });
    }
    
    function autoResize(e) {
      const el = e.target;
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 120) + 'px';
    }
    
    // History sessions
    async function loadSessions() {
      try {
        const res = await fetch(`${API}/api/qa/history?per_page=50`);
        const data = await res.json();
        chatSessions.value = (data.records || []).map(r => ({
          id: r.id,
          title: r.question.length > 30 ? r.question.substring(0, 30) + '...' : r.question,
          time: r.created_time || ''
        }));
      } catch (e) { console.error(e); }
    }

    async function deleteHistoryItem(id) {
      try {
        await fetch(`${API}/api/qa/${id}`, { method: 'DELETE' });
        chatSessions.value = chatSessions.value.filter(s => s.id !== id);
        if (currentSessionId.value === id) {
          currentSessionId.value = null;
          messages.value = [];
        }
      } catch (e) { console.error(e); }
    }
    
    return {
      loading, loggedIn, user, loginForm, loginError, logging,
      sidebarOpen, currentView, question, framework, messages, thinking,
      chatSessions, currentSessionId,
      doLogin, doLogout, newChat, switchChat, sendMessage,
      askSample, scrollToBottom, autoResize,
      loadSessions, deleteHistoryItem,
      renderMarkdown
    };
  }
};

createApp(App).mount('#app');
