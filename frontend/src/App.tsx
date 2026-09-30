import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { LoginPage } from './pages/LoginPage';
import { useWebSocket } from './hooks/useWebSocket';
import { Inbox } from './components/Inbox';
import { UserSearch } from './components/UserSearch';
import { ConversationView } from './components/ConversationView';

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
};

const MainLayout = () => {
  useWebSocket();
  const { logout, user } = useAuth();
  const [selectedConv, setSelectedConv] = useState<string | null>(null);
  
  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="flex items-center justify-between px-6 py-4 bg-white border-b">
        <h1 className="text-xl font-semibold">Cross-Tenant Messenger</h1>
        <div className="flex items-center gap-4">
          <span className="text-sm text-gray-600">{user?.email} ({user?.tenant_name})</span>
          <button onClick={logout} className="px-3 py-1 text-sm text-red-600 border border-red-200 rounded hover:bg-red-50">
            Logout
          </button>
        </div>
      </header>
      <main className="flex-1 overflow-hidden">
        <div className="flex h-full max-w-6xl mx-auto border-x bg-white">
          <div className="w-1/3 border-r flex flex-col relative">
            <UserSearch onConversationCreated={setSelectedConv} />
            <div className="flex-1 overflow-hidden">
              <Inbox onSelect={setSelectedConv} selectedId={selectedConv} />
            </div>
          </div>
          <div className="flex-1 flex flex-col">
            {selectedConv ? (
              <ConversationView conversationId={selectedConv} />
            ) : (
              <div className="flex-1 p-8 text-center text-gray-400 flex items-center justify-center">
                Select a conversation to start messaging
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

const AppRoutes = () => {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route 
        path="/" 
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        } 
      />
    </Routes>
  );
};

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <AppRoutes />
      </Router>
    </AuthProvider>
  );
}
