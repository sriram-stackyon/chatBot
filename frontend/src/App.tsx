import './index.css';
import { AuthPanel } from './components/auth/AuthPanel';
import { useAuth } from './hooks/useAuth';
import { ChatPage } from './pages/ChatPage';

export default function App() {
  const { session, loading, error, signIn, signUp, signInWithGoogle, signOut } = useAuth();

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
  return (
    <ChatPage
      accessToken={session.access_token}
      userEmail={email}
      onSignOut={signOut}
    />
  );
}
