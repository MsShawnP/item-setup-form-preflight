import { resolve } from 'path'
import tailwindcss from '@tailwindcss/vite'

export default {
  plugins: [
    tailwindcss(),
  ],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        'schema-diff': resolve(__dirname, 'schema-diff/index.html'),
        'case-study': resolve(__dirname, 'case-study/index.html'),
      },
    },
  },
}
