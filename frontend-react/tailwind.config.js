/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        dark: {
          bg: '#0E1117',
          surface: '#161B22',
          border: '#30363D',
          hover: '#21262D',
          muted: '#8B949E',
          text: '#FAFAFA'
        }
      }
    },
  },
  plugins: [],
}
