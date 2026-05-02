import { createClient } from '@supabase/supabase-js';

const env = import.meta.env as Record<string, string | undefined>;

const supabaseUrl =
  env.VITE_SUPABASE_URL ??
  env.VITE_SUPABASE_PROJECT_URL ??
  env.SUPABASE_URL ??
  env.SUPABASE_PROJECT_URL ??
  '';

const supabaseAnonKey =
  env.VITE_SUPABASE_ANON_KEY ??
  env.VITE_SUPABASE_KEY ??
  env.VITE_SUPABASE_PUBLIC_KEY ??
  env.SUPABASE_ANON_KEY ??
  env.SUPABASE_KEY ??
  '';

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

export const supabaseConfigError = isSupabaseConfigured
  ? null
  : 'Missing Supabase frontend env. Set VITE_SUPABASE_URL (or VITE_SUPABASE_PROJECT_URL) and VITE_SUPABASE_ANON_KEY (or VITE_SUPABASE_KEY).';

export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null;
