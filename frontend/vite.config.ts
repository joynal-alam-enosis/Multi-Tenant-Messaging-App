import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production';

  return {
    plugins: [react()],
    base: '/', // Production: root path. Dev: also root (nginx handles proxy)
    server: {
      port: 3000,
      host: '0.0.0.0',
      // Proxy only used in dev mode (npm run dev)
      proxy: !isProduction ? {
        '/api': {
          target: 'http://backend:8000',
          changeOrigin: true,
        },
        '/ws': {
          target: 'ws://backend:8000',
          ws: true,
        },
        // Browser -> Vite -> MiniStack Cognito (InitiateAuth). Path is rewritten to /.
        '/aws-cognito': {
          target: 'http://ministack:4566',
          changeOrigin: true,
          rewrite: () => '/',
        },
      } : undefined,
    },
    build: {
      outDir: 'dist',
      sourcemap: !isProduction, // Source maps only in dev
      minify: isProduction ? 'esbuild' : false,
      cssCodeSplit: true,
      rollupOptions: {
        output: {
          // Ensure consistent hashing for cache busting
          entryFileNames: 'assets/[name]-[hash].js',
          chunkFileNames: 'assets/[name]-[hash].js',
          assetFileNames: (assetInfo) => {
            const info = assetInfo.name.split('.');
            const ext = info[info.length - 1];
            if (/\.(png|jpe?g|gif|webp|svg|woff2?|ttf|eot)$/.test(assetInfo.name)) {
              return `assets/[name]-[hash].${ext}`;
            }
            if (ext === 'css') {
              return `assets/[name]-[hash].${ext}`;
            }
            return `assets/[name]-[hash].${ext}`;
          },
          manualChunks: {
            // Vendor chunks for better caching
            'vendor-react': ['react', 'react-dom', 'react-router-dom'],
            'vendor-query': ['@tanstack/react-query'],
            'vendor-axios': ['axios'],
          },
        },
      },
      // Chunk size warning limit (default 500kb)
      chunkSizeWarningLimit: 1000,
    },
    // Environment variables with VITE_ prefix are exposed to client
    define: {
      // Ensure process.env is available for libraries that expect it
      'process.env': {},
    },
  };
});