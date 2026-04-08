import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'
import { ChatProvider } from './ChatContext.jsx'
import Login from './pages/Login.jsx'
import Signup from './pages/Signup.jsx'
import Chat from './pages/Chat.jsx'
import Settings from './pages/Settings.jsx'
import Layout from './components/Layout.jsx'

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="auth-container" style={{justifyContent: 'center', color: 'white'}}>Loading...</div>;
  if (!user) return <Navigate to="/login" />;
  return children;
}

function GuestRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="auth-container" style={{justifyContent: 'center', color: 'white'}}>Loading...</div>;
  if (user) return <Navigate to="/" />;
  return children;
}

function App() {
  return (
    <BrowserRouter>
      <ChatProvider>
        <Routes>
          <Route path="/login" element={
            <GuestRoute>
              <Login />
            </GuestRoute>
          } />
          <Route path="/signup" element={
            <GuestRoute>
              <Signup />
            </GuestRoute>
          } />
          
          <Route path="/" element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }>
            <Route index element={<Chat />} />
          </Route>
        </Routes>
      </ChatProvider>
    </BrowserRouter>
  )
}

export default App
