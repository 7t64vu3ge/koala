import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { API_BASE_URL } from '../constants';

export default function Signup() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    display_name: '',
    email: '',
    password: ''
  });
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/signup`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Signup failed');
      }

      // successfully signed up, redirect to login
      navigate('/login');
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card glass">
        <h1 className="auth-title">Join Koala</h1>
        <p style={{textAlign: 'center', color: 'var(--text-secondary)'}}>Create an account to get started.</p>
        
        {error && <div style={{color: 'var(--error-color)', textAlign: 'center', padding: '0.5rem', background: 'rgba(239,68,68,0.1)', borderRadius: '0.5rem'}}>{error}</div>}

        <form onSubmit={handleSubmit} style={{display: 'flex', flexDirection: 'column', gap: '1rem'}}>
          <div>
            <label style={{display: 'block', marginBottom: '0.5rem'}}>Display Name</label>
            <input 
              type="text" 
              className="input" 
              value={formData.display_name} 
              onChange={e => setFormData({...formData, display_name: e.target.value})} 
              required
            />
          </div>
          <div>
            <label style={{display: 'block', marginBottom: '0.5rem'}}>Email</label>
            <input 
              type="email" 
              className="input" 
              value={formData.email} 
              onChange={e => setFormData({...formData, email: e.target.value})} 
              required
            />
          </div>
          <div>
            <label style={{display: 'block', marginBottom: '0.5rem'}}>Password</label>
            <input 
              type="password" 
              className="input" 
              value={formData.password} 
              onChange={e => setFormData({...formData, password: e.target.value})} 
              required
            />
          </div>
          <button type="submit" className="btn btn-primary" style={{marginTop: '1rem'}}>
            Sign Up
          </button>
        </form>
        
        <p style={{textAlign: 'center', marginTop: '1rem'}}>
          Already have an account? <Link to="/login" style={{color: 'var(--accent-color)', textDecoration: 'none'}}>Sign in</Link>
        </p>
      </div>
    </div>
  );
}
