import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          minSize: 16000,
          groups: [
            { name: 'vendor-motion', test: /node_modules\/(?:framer-motion|motion)/ },
            { name: 'vendor-markdown', test: /node_modules\/(?:react-markdown|remark-gfm|unified|remark|rehype|micromark|mdast|hast|vfile)/ },
            { name: 'vendor-supabase', test: /node_modules\/@supabase/ },
            { name: 'vendor-sentry', test: /node_modules\/@sentry/ },
            { name: 'vendor-posthog', test: /node_modules\/(?:posthog-js|@posthog)/ },
            { name: 'vendor-react', test: /node_modules\/(?:react|react-dom|scheduler)/ },
            { name: 'vendor-icons', test: /node_modules\/lucide-react/ },
            { name: 'vendor', test: /node_modules/ },
          ],
        },
      },
    },
  },
})
