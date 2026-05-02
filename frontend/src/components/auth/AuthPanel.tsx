import { FormEvent, useState } from 'react';

const EMPLOYEE_DOMAIN = ((import.meta.env.EMPLOYEE_EMAIL_DOMAIN as string | undefined) ?? '')
  .trim()
  .toLowerCase()
  .replace(/^@/, '');

interface AuthPanelProps {
  onSignIn: (email: string, password: string) => Promise<void>;
  onSignUp: (email: string, password: string, fullName?: string) => Promise<void>;
  onGoogleSignIn: () => void;
  error?: string | null;
}

export function AuthPanel({ onSignIn, onSignUp, onGoogleSignIn, error }: AuthPanelProps) {
  const [isSignup, setIsSignup] = useState(false);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!email.trim() || !password.trim() || (isSignup && !fullName.trim())) return;

    setBusy(true);
    try {
      if (isSignup) {
        await onSignUp(email.trim(), password, fullName.trim());
      } else {
        await onSignIn(email.trim(), password);
      }
    } catch {
      // Parent hook manages error state shown in this form.
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ width: '100%', height: '100%', display: 'grid', placeItems: 'center' }}>
      <form
        onSubmit={(event) => {
          void handleSubmit(event);
        }}
        style={{
          width: 360,
          background: '#0e1f40',
          border: '1px solid #28416a',
          borderRadius: 12,
          padding: 20,
          display: 'grid',
          gap: 12,
        }}
      >
        <h2 style={{ margin: 0, color: '#d9e2f8', fontSize: 20 }}>
          {isSignup ? 'Create Account' : 'Login'}
        </h2>
        <div style={{ color: '#9fb1d7', fontSize: 13 }}>
          {EMPLOYEE_DOMAIN
            ? isSignup
              ? `Register using your @${EMPLOYEE_DOMAIN} work email.`
              : `Sign in with your @${EMPLOYEE_DOMAIN} work email.`
            : isSignup
              ? 'Register with any email and password.'
              : 'Sign in with your email and password.'}
        </div>
        {isSignup && (
          <input
            type="text"
            placeholder="Full name"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            style={{ height: 40, borderRadius: 8, border: '1px solid #365483', padding: '0 10px' }}
            required
          />
        )}
        <input
          type="email"
          placeholder={EMPLOYEE_DOMAIN ? `name@${EMPLOYEE_DOMAIN}` : 'name@example.com'}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          style={{ height: 40, borderRadius: 8, border: '1px solid #365483', padding: '0 10px' }}
          required
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          style={{ height: 40, borderRadius: 8, border: '1px solid #365483', padding: '0 10px' }}
          required
        />
        {error && <div style={{ color: '#f9a2b6', fontSize: 13 }}>{error}</div>}
        <button
          type="submit"
          disabled={busy}
          style={{
            height: 40,
            border: 'none',
            borderRadius: 8,
            background: '#4452ff',
            color: '#fff',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {busy ? 'Please wait...' : isSignup ? 'Create account' : 'Sign in'}
        </button>
        <button
          type="button"
          onClick={onGoogleSignIn}
          style={{
            height: 40,
            border: '1px solid #365483',
            borderRadius: 8,
            background: '#132647',
            color: '#dbe6ff',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Continue with Google
        </button>
        <button
          type="button"
          onClick={() => {
            setIsSignup((prev) => !prev);
            setFullName('');
          }}
          style={{
            height: 36,
            border: '1px solid #365483',
            borderRadius: 8,
            background: 'transparent',
            color: '#c6d3f2',
            cursor: 'pointer',
          }}
        >
          {isSignup ? 'Already have an account? Login' : 'Need an account? Signup'}
        </button>
      </form>
    </div>
  );
}
