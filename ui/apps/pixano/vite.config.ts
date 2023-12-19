import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		proxy: {
		"/datasets": {
			target: "http://127.0.0.1:8000",
			changeOrigin: true,
			secure: false,
		},
		"/models": {
			target: "http://127.0.0.1:8000",
			changeOrigin: true,
			secure: false,
		},
		"/data": {
			target: "http://127.0.0.1:8000",
			changeOrigin: true,
			secure: false,
		},
		},
  },
});
