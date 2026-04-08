import React, { useState } from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { MessageSquare, Settings as SettingsIcon, LogOut, Plus } from 'lucide-react';
import { useAuth } from '../AuthContext';
import { useChat } from '../ChatContext';
import Settings from '../pages/Settings';

export default function Layout() {
  const { user, logout } = useAuth();
  const { sessions, currentSessionId, setCurrentSessionId, createNewSession } = useChat();
  const navigate = useNavigate();
  const location = useLocation();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div style={{ fontWeight: 'bold', fontSize: '1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>🐨</span> Koala
          </div>
        </div>

        <div className="sidebar-content" style={{overflowY: 'auto'}}>
          <p style={{fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem', marginTop: '1rem'}}>
            Actions
          </p>
          <button 
            onClick={createNewSession}
            className="btn btn-ghost" 
            style={{justifyContent: 'flex-start', border: 'none', width: '100%', marginBottom: '0.5rem'}}
          >
            <Plus size={18} /> New Chat
          </button>
          <button 
            onClick={() => setIsSettingsOpen(true)} 
            className="btn btn-ghost" 
            style={{justifyContent: 'flex-start', border: 'none', width: '100%', backgroundColor: isSettingsOpen ? 'var(--bg-surface)' : 'transparent'}}
          >
            <SettingsIcon size={18} /> Settings
          </button>

          <p style={{fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem', marginTop: '2rem'}}>
            Recent Chats
          </p>
          <div style={{display: 'flex', flexDirection: 'column', gap: '0.25rem'}}>
            {sessions.map(session => (
              <button
                key={session.id}
                onClick={() => {
                  setCurrentSessionId(session.id);
                  if (location.pathname !== '/') navigate('/');
                }}
                className="btn btn-ghost"
                style={{
                  justifyContent: 'flex-start',
                  border: 'none',
                  textAlign: 'left',
                  fontSize: '0.9rem',
                  padding: '0.6rem 0.75rem',
                  backgroundColor: currentSessionId === session.id ? 'var(--bg-surface)' : 'transparent',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  width: '100%'
                }}
                title={session.title}
              >
                <MessageSquare size={16} /> {session.title || 'Untitled Chat'}
              </button>
            ))}
            {sessions.length === 0 && (
              <p style={{fontSize: '0.85rem', color: 'var(--text-secondary)', padding: '0 0.75rem', fontStyle: 'italic'}}>
                No sessions yet.
              </p>
            )}
          </div>
        </div>

        <div className="sidebar-footer">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem', background: 'var(--bg-surface)', borderRadius: '0.75rem' }}>
            <div style={{ width: 32, height: 32, borderRadius: '50%', backgroundColor: 'var(--accent-color)', color: '#0f1115', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
              {user.display_name?.charAt(0).toUpperCase()}
            </div>
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <div style={{ fontWeight: 500, fontSize: '0.9rem', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                {user.display_name}
              </div>
            </div>
            <button onClick={handleLogout} className="btn btn-ghost" style={{ padding: '0.5rem', border: 'none', color: 'var(--error-color)' }} title="Logout">
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>

      {isSettingsOpen && (
        <div className="modal-overlay" onClick={() => setIsSettingsOpen(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <Settings onClose={() => setIsSettingsOpen(false)} />
          </div>
        </div>
      )}
    </div>
  );
}
