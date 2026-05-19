import './index.css';
import { useState } from 'react';
import { AuthPanel } from './components/auth/AuthPanel';
import { useAuth } from './hooks/useAuth';
import { ChatPage } from './pages/ChatPage';
import { ResearchAgentPage } from './pages/ResearchAgentPage';
import { SheetAgentPage } from './pages/SheetAgentPage';
import { TicTacToePage } from './pages/TicTacToePage';

type AppView = 'chat' | 'sheets' | 'research' | 'tictactoe';

export default function App() {
  const { session, loading, error, signIn, signUp, signInWithGoogle, signOut } = useAuth();
  const [view, setView] = useState<AppView>('chat');

  if (loading) {
    return <div style={{ display: 'grid', placeItems: 'center', height: '100%' }}>Loading...</div>;
  }

  if (!session) {
    return (
      <AuthPanel
        onSignIn={signIn}
        onSignUp={signUp}
        onGoogleSignIn={signInWithGoogle}
        error={error}
      />
    );
  }

  const email = session.user.email ?? 'employee@amzur.com';

  if (view === 'sheets') {
    return (
      <SheetAgentPage
        accessToken={session.access_token}
        userEmail={email}
        onBack={() => setView('chat')}
      />
    );
  }

  if (view === 'research') {
    return (
      <ResearchAgentPage
        accessToken={session.access_token}
        userEmail={email}
        onBack={() => setView('chat')}
      />
    );
  }

  if (view === 'tictactoe') {
    return (
      <TicTacToePage
        accessToken={session.access_token}
        userEmail={email}
        onBack={() => setView('chat')}
      />
    );
  }

  return (
    <ChatPage
      accessToken={session.access_token}
      userEmail={email}
      onSignOut={signOut}
      onOpenSheetAgent={() => setView('sheets')}
      onOpenResearchAgent={() => setView('research')}
      onOpenTicTacToe={() => setView('tictactoe')}
    />
  );
}
