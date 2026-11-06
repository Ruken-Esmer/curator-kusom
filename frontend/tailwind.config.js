/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Public Sans', 'system-ui', 'sans-serif'],
        serif: ['Georgia', 'serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        teal: {
          50:  '#E1F5EE',
          100: '#9FE1CB',
          500: '#1D9E75',
          700: '#0F6E56',
          900: '#04342C',
        },
      },
    },
  },
  plugins: [],
}
