/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        g: {
          bright: '#ffffff',
          med:    '#a0a0a0',
          dim:    '#777777',
          dark:   '#111111',
          border: '#222222',
        },
      },
      fontFamily: {
        term:    ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        pixel:   ['Inter', 'sans-serif'],
        mono:    ['"Courier New"', '"Monaco"', '"Menlo"', 'monospace'],
        display: ['Chiqueta', 'Inter', 'sans-serif'],
      },
      keyframes: {
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0' },
        },
      },
      animation: {
        blink: 'blink 1s step-end infinite',
      },
    },
  },
  plugins: [],
};
