import React, { createContext, useState, useEffect, useContext, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { API_BASE_URL } from './constants';

const ChatContext = createContext();

export const ChatProvider = ({ children }) => {
  const { token } = useAuth();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(undefined); // undefined = initial, null = explicit new chat
  const [loadingSessions, setLoadingSessions] = useState(false);

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
        // Default to first session if none set and not specifically in "New Chat" mode
        if (data.length > 0 && currentSessionId === undefined) {
          setCurrentSessionId(data[0].id);
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
        const newSession = await res.json();
        // We only set the current ID to "new", we NOT add it to the sessions list 
        // because it doesn't have messages yet.
        setCurrentSessionId(newSession.id);
        return newSession;
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
