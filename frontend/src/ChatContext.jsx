import React, { createContext, useState, useEffect, useContext, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { API_BASE_URL } from './constants';

const ChatContext = createContext();

export const ChatProvider = ({ children }) => {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(() => {
    const saved = sessionStorage.getItem('koala_current_session_id');
    // If we have a saved ID, we use it (even if it's the string "null")
    // otherwise we use undefined to signal a fresh start
    return saved !== null ? (saved === 'null' ? null : saved) : undefined;
  });
  const [loadingSessions, setLoadingSessions] = useState(false);

  useEffect(() => {
    if (currentSessionId !== undefined) {
      sessionStorage.setItem('koala_current_session_id', currentSessionId);
    }
  }, [currentSessionId]);

  const fetchSessions = useCallback(async () => {
    if (!token) return;
    setLoadingSessions(true);
    try {
      const res = await fetch(`${API_BASE_URL}/chat/sessions`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
        // Start with a new session by default on initial load
        if (currentSessionId === undefined) {
          setCurrentSessionId(null);
        }
        // Validate: if the persisted session ID no longer exists in the
        // database (e.g. DB was reset, session was deleted), reset to new chat
        // so we don't send requests to a non-existent session.
        else if (currentSessionId && !data.some(s => s.id === currentSessionId)) {
          console.warn(`Stale session ID "${currentSessionId}" not found in fetched sessions — resetting to new chat.`);
          setCurrentSessionId(null);
        }
      }
    } catch (err) {
      console.error('Failed to fetch sessions:', err);
    } finally {
      setLoadingSessions(false);
    }
  }, [token, currentSessionId]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const createNewSession = () => {
    setCurrentSessionId(null);
    navigate('/');
  };

  const persistNewSession = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE_URL}/chat/sessions`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        return await res.json(); // returns { id: "new" }, caller sets the real ID
      }
    } catch (err) {
      console.error('Failed to persist session:', err);
    }
  };

  const refreshSessions = () => fetchSessions();

  return (
    <ChatContext.Provider value={{ 
      sessions, 
      loadingSessions, 
      refreshSessions, 
      currentSessionId, 
      setCurrentSessionId, 
      createNewSession,
      persistNewSession
    }}>
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => useContext(ChatContext);
