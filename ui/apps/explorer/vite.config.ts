import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [svelte()],
  build: {
    outDir: "../../../pixano/apps/explorer/dist"
  },
  server: {
    proxy: {
      "/datasets": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false
      }
    }
  }
})
