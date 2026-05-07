import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { executePlugin } from './vite-plugins/execute-plugin.js'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    executePlugin()  // Execute Python scripts directly (no separate backend!)
  ]
  // No proxy needed - everything runs on same port!
})
