/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        g: {
          bright: '#00ff41',
          med:    '#00cc33',
          dim:    '#004d14',
          dark:   '#001a00',
          border: '#003300',
        },
      },
      fontFamily: {
        term:  ['VT323', '"Courier New"', 'monospace'],
        pixel: ['"Press Start 2P"', 'monospace'],
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
