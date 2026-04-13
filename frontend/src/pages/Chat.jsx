import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot } from 'lucide-react';
import { useAuth } from '../AuthContext';
import { useChat } from '../ChatContext';
import { API_BASE_URL } from '../constants';
import MessageBubble from '../components/MessageBubble';

export default function Chat() {
  const { user, token } = useAuth();
  const { currentSessionId, sessions, loadingSessions, persistNewSession, setCurrentSessionId, refreshSessions } = useChat();
  const currentSession = sessions.find(s => s.id === currentSessionId);
  const topic = currentSession?.metadata?.topic || currentSession?.title || "New Orchestration";
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  // Greeting logic and effect hooks...
  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return `Good Morning, ${user?.display_name}`;
    if (hour < 18) return `Good Afternoon, ${user?.display_name}`;
    return `Good Evening, ${user?.display_name}`;
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  useEffect(() => {
    // Sync local message state with context data
    // but only if we are not in a loading/sending state to avoid race conditions
    if (!loading) {
      if (currentSessionId && sessions.length > 0) {
        const current = sessions.find(s => s.id === currentSessionId);
        if (current) {
          // Optimization: Only update if the content has actually changed
          // to prevent unnecessary re-renders or cursor jumps
          if (JSON.stringify(current.messages) !== JSON.stringify(messages)) {
            setMessages(current.messages || []);
          }
        }
      } else if (currentSessionId === null) {
        setMessages([]);
      }
    }
  }, [currentSessionId, sessions, loading]);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
      inputRef.current.style.height = `${inputRef.current.scrollHeight}px`;
    }
  }, [input]);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!input.trim() || loading) return;
    
    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      let activeSessionId = currentSessionId;
      if (!activeSessionId) {
        const newSession = await persistNewSession();
        if (newSession) activeSessionId = newSession.id;
        else throw new Error("Failed to persist session");
      }

      const res = await fetch(`${API_BASE_URL}/chat/sessions/${activeSessionId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ content: userMsg, execute: false })
      });
      
      const sessionOut = await res.json();
      if (currentSessionId === null) setCurrentSessionId(sessionOut.id);
      
      setMessages(sessionOut.messages);
      await refreshSessions();
      
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleExecutePlan = async (msgIndex) => {
    // Note: MessengerBubble handles its own localLoading, but we still use global loading
    // to potentially disable other inputs if needed.
    try {
      const res = await fetch(`${API_BASE_URL}/chat/sessions/${currentSessionId}/messages/${msgIndex}/execute`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      if (res.ok) {
        const sessionOut = await res.json();
        setMessages(sessionOut.messages);
        await refreshSessions();
      }
    } catch (err) {
      console.error("Execution failed:", err);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <>
      {currentSessionId && messages.length > 0 && (
        <div className="chat-header glass">
          <div className="topic-text">
            <Bot size={18} className="topic-icon" />
            {topic === "Generating title..." ? "Analyzing Intent..." : topic}
          </div>
          <div className="session-status">
            {loading ? "Agent is reasoning..." : "Session Active"}
          </div>
        </div>
      )}

      <div className="chat-container" ref={scrollRef}>
        {messages.length === 0 ? (
          <div className="greeting-container">
            <div className="greeting-text">{getGreeting()}</div>
            <p style={{color: 'var(--text-secondary)', marginTop: '1rem', fontSize: '1.1rem'}}>
              What would you like to orchestrate today?
            </p>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <MessageBubble 
              key={idx} 
              msg={msg} 
              idx={idx} 
              onExecute={handleExecutePlan} 
              globalLoading={loading}
            />
          ))
        )}
        
        {loading && !messages.some(m => m.status === 'executing') && (
          <div className="message-wrapper assistant">
            <div className="message-bubble assistant">
              <div className="loading-dots">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={scrollRef} style={{ height: '1px' }} />
      </div>

      <div className="fixed-input-container glass">
        <div className="input-box">
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder={loadingSessions ? "Initializing..." : "Type your orchestration prompt..."}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
            rows={1}
            style={{paddingRight: '3.5rem', width: '100%'}}
          />
          <button 
            className="send-btn" 
            onClick={handleSubmit} 
            disabled={!input.trim() || loading}
            type="button"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </>
  );
}
