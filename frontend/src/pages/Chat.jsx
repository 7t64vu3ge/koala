import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, Square } from 'lucide-react';
import { useAuth } from '../AuthContext';
import { useChat } from '../ChatContext';
import { API_BASE_URL } from '../constants';
import MessageBubble from '../components/MessageBubble';
import MarkdownRenderer from '../components/MarkdownRenderer';
import TypewriterText from '../components/TypewriterText';

export default function Chat() {
  const { user, token } = useAuth();
  const { currentSessionId, sessions, loadingSessions, persistNewSession, setCurrentSessionId, refreshSessions } = useChat();
  const currentSession = sessions.find(s => s.id === currentSessionId);
  const topic = currentSession?.metadata?.topic || currentSession?.title || "New Orchestration";
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  const activeEsRef = useRef(null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [executingIndex, setExecutingIndex] = useState(null);

  const [sidebarMessageIndex, setSidebarMessageIndex] = useState(null);
  const [isSidebarExpandedFull, setIsSidebarExpandedFull] = useState(false);
  const [expandedSubtaskId, setExpandedSubtaskId] = useState(null);
  const [typingSubtaskId, setTypingSubtaskId] = useState(null);

  // Auto-abort SSE stream on component unmount
  useEffect(() => {
    return () => {
      if (activeEsRef.current) {
        activeEsRef.current.close();
      }
    };
  }, []);

  // Fetch sidebar items
  const activeSidebarMsg = sidebarMessageIndex !== null ? messages[sidebarMessageIndex] : null;
  const sidebarSubtasks = activeSidebarMsg?.subtasks || [];

  // Auto-accordion logic: expand the running subtask automatically, collapse it and open next when finished
  // BUT keep the accordion open if a typewriter is still revealing text for a completed subtask.
  useEffect(() => {
    // If we're still typing out a subtask result, pin that accordion open
    if (typingSubtaskId !== null) {
      setExpandedSubtaskId(typingSubtaskId);
      return;
    }

    const runningTask = sidebarSubtasks.find(st => st.status === 'running');
    if (runningTask) {
      setExpandedSubtaskId(runningTask.id);
    } else {
      // If nothing is running but we are executing, auto-expand the last finished one to show progress
      if (activeSidebarMsg?.status === 'executing') {
        const lastDoneTask = [...sidebarSubtasks].reverse().find(st => st.status === 'done');
        if (lastDoneTask) {
          setExpandedSubtaskId(lastDoneTask.id);
        }
      }
    }
  }, [sidebarSubtasks, activeSidebarMsg?.status, typingSubtaskId]);

  const getSidebarUserPrompt = () => {
    if (sidebarMessageIndex === null || sidebarMessageIndex === 0) return '';
    for (let i = sidebarMessageIndex - 1; i >= 0; i--) {
      if (messages[i].role === 'user') {
        return messages[i].content;
      }
    }
    return '';
  };
  const sidebarUserPrompt = getSidebarUserPrompt();

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
    setError(null);
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setLoading(true);

    try {
      let activeSessionId = currentSessionId;
      if (!activeSessionId) {
        const newSession = await persistNewSession();
        if (newSession) activeSessionId = newSession.id; // still "new", backend handles it
        else throw new Error("Failed to persist session");
      }

      let res = await fetch(`${API_BASE_URL}/chat/sessions/${activeSessionId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ content: userMsg, execute: false })
      });

      // Auto-recovery: if the session no longer exists (stale ID from
      // sessionStorage), transparently retry as a brand-new session.
      if (res.status === 404 && activeSessionId !== 'new') {
        console.warn(`Session ${activeSessionId} not found — creating a new session and retrying.`);
        activeSessionId = 'new';
        res = await fetch(`${API_BASE_URL}/chat/sessions/new/messages`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ content: userMsg, execute: false })
        });
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.detail || `Server error ${res.status}`);
      }

      const sessionOut = await res.json();
      // Always sync the real session ID returned by the backend
      setCurrentSessionId(sessionOut.id);
      setMessages(sessionOut.messages || []);
      await refreshSessions();
      
    } catch (err) {
      console.error(err);
      setError(err.message || 'Something went wrong. Please try again.');
      // Remove the optimistic user message on failure
      setMessages(prev => prev.filter((_, i) => i !== prev.length - 1));
    } finally {
      setLoading(false);
    }
  };

  const handleStopExecution = () => {
    if (activeEsRef.current) {
      activeEsRef.current.close();
      activeEsRef.current = null;
    }
    setIsExecuting(false);
    setLoading(false);
    if (executingIndex !== null) {
      setMessages(prev => prev.map((m, i) =>
        i === executingIndex ? { ...m, status: 'error', content: 'Execution stopped by user.' } : m
      ));
      setExecutingIndex(null);
    }
    refreshSessions();
  };

  const handleExecutePlan = (msgIndex) => {
    const url = `${API_BASE_URL}/chat/sessions/${currentSessionId}/messages/${msgIndex}/execute/stream?token=${token}`;
    const es = new EventSource(url);
    activeEsRef.current = es;
    setIsExecuting(true);
    setExecutingIndex(msgIndex);
    setSidebarMessageIndex(msgIndex); // Automatically slide open right sidebar on execution start!

    // Optimistically mark the message as executing
    setMessages(prev => prev.map((m, i) =>
      i === msgIndex ? { ...m, status: 'executing' } : m
    ));

    es.addEventListener('subtask_started', (e) => {
      const { id } = JSON.parse(e.data);
      setMessages(prev => prev.map((m, i) => {
        if (i !== msgIndex) return m;
        return {
          ...m,
          subtasks: m.subtasks.map(st => st.id === id ? { ...st, status: 'running' } : st)
        };
      }));
    });

    es.addEventListener('subtask_done', (e) => {
      const { id, result } = JSON.parse(e.data);
      setTypingSubtaskId(id); // Start typewriter reveal for this subtask
      setMessages(prev => prev.map((m, i) => {
        if (i !== msgIndex) return m;
        return {
          ...m,
          subtasks: m.subtasks.map(st => st.id === id ? { ...st, status: 'done', result } : st)
        };
      }));
    });

    es.addEventListener('synthesis_started', () => {
      // Clear plan introduction message to start rendering synthesized output cleanly
      setMessages(prev => prev.map((m, i) =>
        i === msgIndex ? { ...m, content: '', isSynthesizing: true } : m
      ));
    });

    es.addEventListener('token', (e) => {
      const { text } = JSON.parse(e.data);
      setMessages(prev => prev.map((m, i) =>
        i === msgIndex ? { ...m, content: m.content + text } : m
      ));
    });

    es.addEventListener('complete', (e) => {
      const { final_output } = JSON.parse(e.data);
      setMessages(prev => prev.map((m, i) =>
        i === msgIndex ? { ...m, status: 'completed', content: final_output, isSynthesizing: false } : m
      ));
      es.close();
      activeEsRef.current = null;
      setIsExecuting(false);
      setExecutingIndex(null);
      refreshSessions();
    });

    es.addEventListener('error', (e) => {
      try {
        const { detail } = JSON.parse(e.data);
        setMessages(prev => prev.map((m, i) =>
          i === msgIndex ? { ...m, status: 'error', content: `Execution failed: ${detail}`, isSynthesizing: false } : m
        ));
      } catch (_) {}
      es.close();
      activeEsRef.current = null;
      setIsExecuting(false);
      setExecutingIndex(null);
    });

    // Fallback: native onerror fires on connection drop
    es.onerror = () => {
      es.close();
      if (activeEsRef.current === es) {
        activeEsRef.current = null;
        setIsExecuting(false);
        setExecutingIndex(null);
      }
    };
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="chat-layout-wrapper">
      {/* 1. Main Chat Window */}
      <div className={`chat-main-window ${isSidebarExpandedFull ? 'hidden' : ''}`}>
        {currentSessionId && messages.length > 0 && (
          <div className="chat-header glass">
            <div className="topic-text">
              <Bot size={18} className="topic-icon" />
              {topic === "Generating title..." ? "Analyzing Intent..." : topic}
            </div>
            <div className="session-status">
              {isExecuting ? "Executing orchestration..." : loading ? "Agent is reasoning..." : "Session Active"}
            </div>
          </div>
        )}

        <div className="chat-container" ref={scrollRef}>
          {error && (
            <div style={{ margin: '1rem auto', padding: '0.75rem 1rem', background: 'var(--error, #ff4d4f22)', border: '1px solid #ff4d4f', borderRadius: '8px', color: '#ff4d4f', maxWidth: '600px' }}>
              ⚠️ {error}
            </div>
          )}
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
                globalLoading={loading || isExecuting}
                onShowDetails={(msgIdx) => {
                  setSidebarMessageIndex(msgIdx);
                  setIsSidebarExpandedFull(true);
                }}
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
              disabled={loading || isExecuting}
              rows={1}
              style={{paddingRight: '3.5rem', width: '100%'}}
            />
            {isExecuting ? (
              <button 
                className="send-btn stop-btn" 
                onClick={handleStopExecution} 
                title="Stop Generation"
                type="button"
                style={{ backgroundColor: 'var(--error-color, #ff4d4f)', color: 'white' }}
              >
                <Square size={16} fill="white" />
              </button>
            ) : (
              <button 
                className="send-btn" 
                onClick={handleSubmit} 
                disabled={!input.trim() || loading}
                type="button"
              >
                <Send size={18} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* 2. Right Sidebar for Subtask Execution Accordion Dashboard */}
      {sidebarMessageIndex !== null && activeSidebarMsg && (
        <aside className={`subtask-execution-sidebar glass ${isSidebarExpandedFull ? 'full-width' : ''}`}>
          <div className="sidebar-top-bar">
            <div className="sidebar-title">
              {isSidebarExpandedFull && (
                <button 
                  className="sidebar-back-btn" 
                  onClick={() => setIsSidebarExpandedFull(false)}
                  type="button"
                >
                  &larr; Back to Chat
                </button>
              )}
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                ⚙️ Workflow Execution Plan
              </span>
            </div>
            <button 
              className="modal-close-btn" 
              onClick={() => {
                setSidebarMessageIndex(null);
                setIsSidebarExpandedFull(false);
              }}
              type="button"
              style={{ position: 'static', padding: '0.35rem 0.6rem' }}
              title="Close Sidebar"
            >
              &times;
            </button>
          </div>
          <div className="sidebar-scroll-content">
            {sidebarUserPrompt && (
              <div className="subtask-user-header animate-in">
                <strong>You asked:</strong>
                <p style={{ marginTop: '0.25rem', fontStyle: 'italic', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  "{sidebarUserPrompt}"
                </p>
              </div>
            )}
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }} className="animate-in">
              {sidebarSubtasks.map((task, tidx) => {
                const isExpanded = expandedSubtaskId === task.id;
                return (
                  <div 
                    key={tidx} 
                    className={`accordion-item ${task.status === 'running' ? 'running' : task.status === 'done' ? 'done' : ''} ${isExpanded ? 'expanded' : ''}`}
                  >
                    <button 
                      className="accordion-header"
                      onClick={() => setExpandedSubtaskId(isExpanded ? null : task.id)}
                      type="button"
                    >
                      <div className="accordion-title-block">
                        <span className={`status-dot ${task.status === 'done' ? 'done' : task.status === 'running' ? 'active' : 'idle'}`}></span>
                        <strong style={{ fontSize: '0.85rem' }}>Step {task.id}</strong>
                        <span className={`model-tag ${task.assigned_model.includes('3.3') || task.assigned_model.includes('120b') ? 'expert' : 'advanced'}`} style={{ transform: 'scale(0.85)', originX: 0 }}>
                          {task.assigned_model.split('/').pop()}
                        </span>
                      </div>
                      <span className="accordion-chevron-icon" style={{ fontSize: '0.8rem' }}>
                        &#9660;
                      </span>
                    </button>
                    <div className="accordion-content">
                      <div className="accordion-body-padding">
                        <div className="subtask-desc-sidebar">{task.description}</div>
                        {task.result && (
                          <div className={`subtask-result-sidebar ${task.status === 'done' ? 'completed' : ''}`}>
                            <div className="result-label" style={{ fontSize: '0.75rem' }}>Output:</div>
                            <div className="result-text" style={{ fontSize: '0.8rem' }}>
                              {typingSubtaskId === task.id ? (
                                <TypewriterText
                                  content={task.result}
                                  speed={15}
                                  charsPerTick={4}
                                  onComplete={() => setTypingSubtaskId(null)}
                                />
                              ) : (
                                <MarkdownRenderer content={task.result} />
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </aside>
      )}
    </div>
  );
}
