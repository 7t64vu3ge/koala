import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    try {
      const res = await fetch('http://localhost:8000/auth/signin', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password })
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Login failed');
      }

      const data = await res.json();
      login(data.access_token);
      navigate('/');
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card glass">
        <h1 className="auth-title">Welcome back to Koala</h1>
        <p style={{textAlign: 'center', color: 'var(--text-secondary)'}}>Sign in to continue orchestrating</p>
        
        {error && <div style={{color: 'var(--error-color)', textAlign: 'center', padding: '0.5rem', background: 'rgba(239,68,68,0.1)', borderRadius: '0.5rem'}}>{error}</div>}

        <form onSubmit={handleSubmit} style={{display: 'flex', flexDirection: 'column', gap: '1rem'}}>
          <div>
            <label style={{display: 'block', marginBottom: '0.5rem'}}>Email</label>
            <input 
              type="email" 
              className="input" 
              value={email} 
              onChange={e => setEmail(e.target.value)} 
              required
            />
          </div>
          <div>
            <label style={{display: 'block', marginBottom: '0.5rem'}}>Password</label>
            <input 
              type="password" 
              className="input" 
              value={password} 
              onChange={e => setPassword(e.target.value)} 
              required
            />
          </div>
          <button type="submit" className="btn btn-primary" style={{marginTop: '1rem'}}>
            Sign In
          </button>
        </form>
        
        <p style={{textAlign: 'center', marginTop: '1rem'}}>
          Don't have an account? <Link to="/signup" style={{color: 'var(--accent-color)', textDecoration: 'none'}}>Sign up</Link>
        </p>
      </div>
    </div>
  );
}
