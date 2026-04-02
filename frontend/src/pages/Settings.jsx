import React, { useState } from 'react';
import { useAuth } from '../AuthContext';

export default function Settings() {
  const { user, token, updateUserSettings } = useAuth();
  const [displayName, setDisplayName] = useState(user.display_name || '');
  const [theme, setLocalTheme] = useState(user.theme || 'dark');
  const [message, setMessage] = useState('');

  const handleSave = async (e) => {
    e.preventDefault();
    setMessage('');
    try {
      const res = await fetch('http://localhost:8000/users/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ display_name: displayName, theme })
      });
      if (res.ok) {
        updateUserSettings({ display_name: displayName, theme });
        setMessage('Settings updated successfully!');
      } else {
        setMessage('Failed to update settings');
      }
    } catch (err) {
      setMessage('Error updating settings');
    }
  };

  const handleClearHistory = async () => {
    if (!window.confirm("Are you sure you want to clear all chat sessions?")) return;
    try {
      const res = await fetch('http://localhost:8000/chat/sessions', {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setMessage('Chat history cleared.');
      }
    } catch (err) {
      setMessage('Error clearing history');
    }
  };

  return (
    <div className="settings-container">
      <h1 style={{fontSize: '2rem', fontWeight: 'bold'}}>Settings</h1>
      
      {message && <div style={{padding: '1rem', backgroundColor: 'var(--bg-surface)', borderRadius: '0.5rem', borderLeft: '4px solid var(--accent-color)'}}>{message}</div>}

      <form onSubmit={handleSave} className="settings-section">
        <h2>Profile & Preferences</h2>
        
        <div>
          <label style={{display: 'block', marginBottom: '0.5rem'}}>Display Name</label>
          <input 
            type="text" 
            className="input" 
            value={displayName} 
            onChange={e => setDisplayName(e.target.value)} 
          />
        </div>

        <div>
           <label style={{display: 'block', marginBottom: '0.5rem'}}>Theme</label>
           <select 
             className="input" 
             value={theme}
             onChange={e => setLocalTheme(e.target.value)}
           >
             <option value="dark">Dark Mode</option>
             <option value="light">Light Mode</option>
           </select>
        </div>

        <div style={{marginTop: '1rem'}}>
          <button type="submit" className="btn btn-primary">Save Settings</button>
        </div>
      </form>

      <div className="settings-section">
        <h2>Data Management</h2>
        <p style={{color: 'var(--text-secondary)', marginBottom: '1rem', lineHeight: '1.5'}}>
          Clearing history will permanently delete all your conversation data. This action cannot be undone.
        </p>
        <div>
          <button onClick={handleClearHistory} className="btn" style={{backgroundColor: 'rgba(239, 68, 68, 0.1)', color: 'var(--error-color)', border: '1px solid rgba(239, 68, 68, 0.2)'}}>
            Clear All History
          </button>
        </div>
      </div>
    </div>
  );
}
