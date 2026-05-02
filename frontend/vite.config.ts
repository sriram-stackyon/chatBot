import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
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
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
