import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot } from 'lucide-react';
import { useAuth } from '../AuthContext';

export default function Chat() {
  const { user, token } = useAuth();
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  // Time based greeting
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
    const fetchSession = async () => {
      setSessionLoading(true);
      try {
        const res = await fetch('http://localhost:8000/chat/sessions', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!res.ok) throw new Error('Failed to fetch sessions');
        const sessions = await res.json();
        
        if (Array.isArray(sessions) && sessions.length > 0) {
          setSessionId(sessions[0].id);
          setMessages(sessions[0].messages || []);
        } else {
          const createRes = await fetch('http://localhost:8000/chat/sessions', {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
          });
          const newSession = await createRes.json();
          setSessionId(newSession.id);
        }
      } catch (err) {
        console.error('Session error:', err);
      } finally {
        setSessionLoading(false);
      }
    };
    if (token) fetchSession();
  }, [token]);

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!input.trim() || !sessionId || loading) return;
    
    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      const res = await fetch(`http://localhost:8000/chat/sessions/${sessionId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ content: userMsg, execute: true })
      });
      
      const sessionOut = await res.json();
      setMessages(sessionOut.messages);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
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
            <div key={idx} className={`message ${msg.role}`}>
              <div className="message-avatar">
                {msg.role === 'user' ? user?.display_name?.charAt(0).toUpperCase() : <Bot size={20} />}
              </div>
              <div className="message-content">
                <div style={{fontWeight: 600, marginBottom: '0.25rem', color: msg.role === 'user' ? 'var(--text-primary)' : 'var(--accent-color)'}}>
                  {msg.role === 'user' ? 'You' : 'Koala'}
                </div>
                <div style={{whiteSpace: 'pre-wrap'}}>{msg.content}</div>
                
                {msg.subtasks && msg.subtasks.length > 0 && (
                  <div style={{marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem'}}>
                    <div style={{fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)'}}>
                      Execution Plan
                    </div>
                    {msg.subtasks.map((task, tidx) => (
                      <div key={tidx} className="subtask-box">
                        <div className="subtask-header">{task.id} — Assigned to: <span style={{color: 'var(--accent-color)'}}>{task.assigned_model}</span></div>
                        <div style={{color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '0.5rem'}}>{task.description}</div>
                        <div style={{fontSize: '0.85rem', padding: '0.5rem', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '0.25rem', borderLeft: '3px solid var(--accent-color)'}}>
                          <strong>Result:</strong> {task.result || 'Pending / Not Executed'}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        
        {loading && (
          <div className="message assistant">
            <div className="message-avatar"><Bot size={20} /></div>
            <div className="message-content">
              <div style={{fontWeight: 600, marginBottom: '0.25rem', color: 'var(--accent-color)'}}>Koala</div>
              <div style={{display: 'flex', gap: '0.5rem', alignItems: 'center', margin: '0.5rem 0'}}>
                <span style={{display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--text-secondary)', animation: 'pulse 1.5s infinite'}}></span>
                <span style={{display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--text-secondary)', animation: 'pulse 1.5s infinite', animationDelay: '0.2s'}}></span>
                <span style={{display: 'inline-block', width: '8px', height: '8px', borderRadius: '50%', backgroundColor: 'var(--text-secondary)', animation: 'pulse 1.5s infinite', animationDelay: '0.4s'}}></span>
              </div>
            </div>
            <style dangerouslySetInnerHTML={{__html: `
              @keyframes pulse {
                0%, 100% { opacity: 0.4; transform: scale(0.8); }
                50% { opacity: 1; transform: scale(1); }
              }
            `}} />
          </div>
        )}
      </div>

      <div className="fixed-input-container glass">
        <div className="input-box">
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder={sessionLoading ? "Initializing session..." : "Type your orchestration prompt..."}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sessionLoading || loading}
            rows={1}
            style={{paddingRight: '3.5rem', width: '100%'}}
          />
          <button 
            className="send-btn" 
            onClick={handleSubmit} 
            disabled={!input.trim() || loading || sessionLoading}
            type="button"
          >
            <Send size={18} />
          </button>
        </div>
      </div>
    </>
  );
}
