import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    watch: {
      usePolling: true, // Docker 컨테이너 볼륨 마운트 환경에서 HMR(Hot Module Replacement) 지원
    },
  },
});
