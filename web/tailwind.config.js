/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: '#0f1419',
        panel: '#1a212b',
        ink: '#e6edf3',
        muted: '#8b97a7',
        line: '#2a3441',
        consensus: '#3fb950',
        contested: '#f0883e',
        outlier: '#58a6ff',
      },
    },
  },
  plugins: [],
}
