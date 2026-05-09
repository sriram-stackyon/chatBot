import { useEffect, useState } from 'react';

import {
  buildGoogleLoginUrl,
  getMe,
  signIn as signInRequest,
  signUp as signUpRequest,
} from '../lib/api';

interface LocalSession {
  access_token: string;
  user: {
    id: string;
    email: string | null;
  };
}

const AUTH_TOKEN_KEY = 'amzur_auth_token';
const AUTH_EMAIL_KEY = 'amzur_auth_email';
const AUTH_USER_ID_KEY = 'amzur_auth_user_id';
const EMPLOYEE_DOMAIN = ((import.meta.env.EMPLOYEE_EMAIL_DOMAIN as string | undefined) ?? '')
  .trim()
  .toLowerCase()
  .replace(/^@/, '');

interface AuthState {
  session: LocalSession | null;
  loading: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, fullName?: string) => Promise<void>;
  signInWithGoogle: () => void;
  signOut: () => Promise<void>;
}

export function useAuth(): AuthState {
  const [session, setSession] = useState<LocalSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function saveSession(next: LocalSession): void {
    localStorage.setItem(AUTH_TOKEN_KEY, next.access_token);
    localStorage.setItem(AUTH_USER_ID_KEY, next.user.id);
    localStorage.setItem(AUTH_EMAIL_KEY, next.user.email ?? '');
    setSession(next);
  }

  function clearSession(): void {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_ID_KEY);
    localStorage.removeItem(AUTH_EMAIL_KEY);
    setSession(null);
  }

  useEffect(() => {
    const currentUrl = new URL(window.location.href);
    const isGoogleCallback = currentUrl.pathname === '/auth/google/callback';
    if (isGoogleCallback) {
      const token = currentUrl.searchParams.get('token');
      const id = currentUrl.searchParams.get('id') ?? '';
      const email = currentUrl.searchParams.get('email');
      if (token) {
        saveSession({
          access_token: token,
          user: {
            id,
            email,
          },
        });
        window.history.replaceState({}, '', '/');
        setLoading(false);
        return;
      }
    }

    let active = true;
    const token = localStorage.getItem(AUTH_TOKEN_KEY);
    const cachedEmail = localStorage.getItem(AUTH_EMAIL_KEY);
    const cachedUserId = localStorage.getItem(AUTH_USER_ID_KEY);

    if (!token) {
      setLoading(false);
      return;
    }

    void getMe(token)
      .then((me) => {
        if (!active) return;
        saveSession({
          access_token: token,
          user: {
            id: me.id || cachedUserId || '',
            email: me.email ?? cachedEmail,
          },
        });
      })
      .catch(() => {
        if (!active) return;
        clearSession();
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  function toMessage(error: unknown, fallback: string): string {
    if (error instanceof Error && error.message) return error.message;
    if (typeof error === 'string' && error.trim()) return error;
    return fallback;
  }

  function assertEmployeeEmail(email: string): void {
    if (!EMPLOYEE_DOMAIN) return;

    const normalized = email.trim().toLowerCase();
    if (!normalized.endsWith(`@${EMPLOYEE_DOMAIN}`)) {
      throw new Error(`Use your @${EMPLOYEE_DOMAIN} employee email.`);
    }
  }

  async function signIn(email: string, password: string): Promise<void> {
    try {
      setError(null);
      assertEmployeeEmail(email);
      const response = await signInRequest(email.trim().toLowerCase(), password);
      saveSession({ access_token: response.access_token, user: response.user });
    } catch (err) {
      const message = toMessage(err, 'Sign in failed');
      setError(message);
      throw err;
    }
  }

  async function signUp(email: string, password: string, fullName?: string): Promise<void> {
    try {
      setError(null);
      assertEmployeeEmail(email);
      const response = await signUpRequest(email.trim().toLowerCase(), password, fullName);
      saveSession({ access_token: response.access_token, user: response.user });
    } catch (err) {
      const message = toMessage(err, 'Sign up failed');
      setError(message);
      throw err;
    }
  }

  async function signOut(): Promise<void> {
    setError(null);
    clearSession();
  }

  function signInWithGoogle(): void {
    const loginUrl = buildGoogleLoginUrl('/auth/google/callback');
    window.location.assign(loginUrl);
  }

  return { session, loading, error, signIn, signUp, signInWithGoogle, signOut };
}
