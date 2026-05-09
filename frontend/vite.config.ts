import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '../backend', '');
  const proxyTarget = env.VITE_API_BASE_URL || env.API_BASE_URL || 'http://localhost:8000';

  return {
    // Load environment variables from backend/.env so frontend and backend stay in sync.
    envDir: '../backend',
    // Expose only safe, public Supabase variables to the client bundle.
    envPrefix: [
      'VITE_',
      'SUPABASE_URL',
      'SUPABASE_PROJECT_URL',
      'SUPABASE_ANON_KEY',
      'SUPABASE_KEY',
      'API_BASE_URL',
      'EMPLOYEE_EMAIL_DOMAIN',
    ],
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
