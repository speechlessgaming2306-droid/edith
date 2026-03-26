import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
const isWebBuild = process.env.VITE_BUILD_TARGET === 'web'

export default defineConfig({
    plugins: [react()],
    base: isWebBuild ? '/' : './',
    server: {
        host: '0.0.0.0',
        port: 5173,
        strictPort: true,
    }
})
