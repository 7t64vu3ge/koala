import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot } from 'lucide-react';
import { useAuth } from '../AuthContext';
import { useChat } from '../ChatContext';
import { API_BASE_URL } from '../constants';

export default function Chat() {
  const { user, token } = useAuth();
  const { currentSessionId, sessions, loadingSessions, persistNewSession, setCurrentSessionId, refreshSessions } = useChat();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const [expandedMessages, setExpandedMessages] = useState({});

  const toggleDetails = (idx) => {
    setExpandedMessages(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }));
  };

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
    // Only sync if we aren't currently waiting for a response (loading)
    // to prevent local optimistic messages from being cleared
    if (!loading) {
      if (currentSessionId && sessions.length > 0) {
        const current = sessions.find(s => s.id === currentSessionId);
        if (current) {
          setMessages(current.messages || []);
        }
      } else if (currentSessionId === null) {
        setMessages([]);
      }
    }
  }, [currentSessionId, sessions, loading]);

  // Auto-focus input and resize
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
    // Optimistic update
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      let activeSessionId = currentSessionId;
      
      // If in New Chat mode, persist to DB now
      if (!activeSessionId) {
        const newSession = await persistNewSession();
        if (newSession) {
          activeSessionId = newSession.id;
        } else {
          throw new Error("Failed to persist session");
        }
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
      
      if (activeSessionId === "new") {
        setCurrentSessionId(sessionOut.id);
        refreshSessions();
      }
      
      setMessages(sessionOut.messages);
      
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleExecutePlan = async (msgIndex) => {
    setLoading(true);
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
        refreshSessions();
      }
    } catch (err) {
      console.error("Execution failed:", err);
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
            <div key={idx} className={`message-wrapper ${msg.role}`}>
              <div className={`message-bubble ${msg.role}`}>
                <div className="message-header">
                  {msg.role === 'user' ? 'You' : 'Koala'}
                </div>
                <div className="message-content">{msg.content}</div>
                
                {msg.subtasks && msg.subtasks.length > 0 && (
                  <div className="orchestration-section">
                    <button 
                      className="details-toggle-btn"
                      onClick={() => toggleDetails(idx)}
                    >
                      {expandedMessages[idx] ? 'Hide Orchestration Details' : 'Show Orchestration Details'}
                    </button>
                    
                    {expandedMessages[idx] && (
                      <div className="subtasks-container">
                        <div className="subtasks-label">
                          {msg.status === 'pending_approval' ? 'Proposed Execution Plan:' : 'Orchestration Workflow:'}
                        </div>
                        {msg.subtasks.map((task, tidx) => (
                          <div key={tidx} className="subtask-card">
                            <div className="subtask-card-header">
                              <span className={`status-dot ${task.result ? 'done' : (msg.status === 'executing' ? 'active' : 'idle')}`}></span>
                              <strong>Step {task.id}</strong> — <span className="model-tag">{task.assigned_model}</span>
                            </div>
                            <div className="subtask-desc">{task.description}</div>
                            {task.result && (
                              <div className="subtask-result">
                                <div className="result-label">Result:</div>
                                <div className="result-text">{task.result}</div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {msg.role === 'assistant' && ['pending_approval', 'error'].includes(msg.status) && (
                  <div className="plan-approval-actions">
                    <button 
                      className="execute-btn" 
                      onClick={() => handleExecutePlan(idx)}
                      disabled={loading}
                    >
                      {loading ? 'Wait...' : 'Confirm & Execute Orchestration'}
                    </button>
                    <div className="refine-tip">
                      Or type your feedback below to refine this plan...
                    </div>
                  </div>
                )}

                {msg.status === 'executing' && (
                  <div className="distributing-status">
                    <div className="pulse-loader"></div>
                    Agents are distributed and working on subtasks...
                  </div>
                )}
              </div>
            </div>
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
