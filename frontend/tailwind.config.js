/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class'],
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: {
          void: '#07090E',
          subtle: '#090D15',
        },
        glass: {
          surface: '#0C101A',
          raised: '#121826',
          overlay: '#161F32',
          border: 'rgba(255, 255, 255, 0.08)',
          'border-highlight': 'rgba(255, 255, 255, 0.16)',
        },
        telemetry: {
          cyan: '#00F0FF',
          'cyan-glow': 'rgba(0, 240, 255, 0.35)',
          emerald: '#00FF9D',
          'emerald-glow': 'rgba(0, 255, 157, 0.35)',
          amber: '#F59E0B',
          'amber-glow': 'rgba(245, 158, 11, 0.35)',
          crimson: '#FF3366',
          'crimson-glow': 'rgba(255, 51, 102, 0.40)',
          purple: '#A855F7',
          'purple-glow': 'rgba(168, 85, 247, 0.35)',
        },
      },
      fontFamily: {
        sans: ['Geist Sans', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'glow-cyan': '0 0 20px -3px rgba(0, 240, 255, 0.45)',
        'glow-emerald': '0 0 20px -3px rgba(0, 255, 157, 0.45)',
        'glow-crimson': '0 0 24px -2px rgba(255, 51, 102, 0.50)',
        'glow-amber': '0 0 16px -2px rgba(245, 158, 11, 0.40)',
        'glass-panel': '0 8px 32px 0 rgba(0, 0, 0, 0.75)',
        'glass-inset': 'inset 0 1px 0 0 rgba(255, 255, 255, 0.08)',
      },
    },
  },
  plugins: [],
};
