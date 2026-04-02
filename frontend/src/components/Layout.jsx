import React from 'react';
import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom';
import { MessageSquare, Settings, LogOut, Plus } from 'lucide-react';
import { useAuth } from '../AuthContext';

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <div style={{fontWeight: 'bold', fontSize: '1.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
            <span>🐨</span> Koala
          </div>
          <button onClick={() => navigate('/')} className="btn btn-ghost" style={{padding: '0.5rem'}} title="New Chat">
            <Plus size={20} />
          </button>
        </div>
        
        <div className="sidebar-content">
          <p style={{fontSize: '0.8rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.5rem', marginTop: '1rem'}}>
            Menu
          </p>
          <Link to="/" className="btn btn-ghost" style={{justifyContent: 'flex-start', border: 'none', backgroundColor: location.pathname === '/' ? 'var(--bg-surface)' : 'transparent'}}>
            <MessageSquare size={18} /> Chat
          </Link>
          <Link to="/settings" className="btn btn-ghost" style={{justifyContent: 'flex-start', border: 'none', backgroundColor: location.pathname === '/settings' ? 'var(--bg-surface)' : 'transparent'}}>
            <Settings size={18} /> Settings
          </Link>
        </div>
        
        <div className="sidebar-footer">
          <div style={{display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem', background: 'var(--bg-surface)', borderRadius: '0.75rem'}}>
            <div style={{width: 32, height: 32, borderRadius: '50%', backgroundColor: 'var(--accent-color)', color: '#0f1115', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold'}}>
              {user.display_name?.charAt(0).toUpperCase()}
            </div>
            <div style={{flex: 1, overflow: 'hidden'}}>
              <div style={{fontWeight: 500, fontSize: '0.9rem', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden'}}>
                {user.display_name}
              </div>
            </div>
            <button onClick={handleLogout} className="btn btn-ghost" style={{padding: '0.5rem', border: 'none', color: 'var(--error-color)'}} title="Logout">
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>
      
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
