/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        'terminal-bg': '#0a0e17',
        'terminal-card': '#0f1623',
        'terminal-card2': '#131c2e',
        'terminal-border': '#1e2d40',
        'terminal-green': '#00ff88',
        'terminal-red': '#ff4466',
        'terminal-yellow': '#ffd700',
        'terminal-blue': '#00aaff',
        'terminal-purple': '#a855f7',
        'terminal-muted': '#4a6080',
        'terminal-text': '#c8d8e8',
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', '"Cascadia Code"', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s ease-in-out infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 4px rgba(0,255,136,0.3)' },
          '100%': { boxShadow: '0 0 12px rgba(0,255,136,0.7)' },
        }
      }
    },
  },
  plugins: [],
}
