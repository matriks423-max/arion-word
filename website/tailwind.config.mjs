export default {
  content: ['./src/**/*.{astro,html,js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        void: '#060608',
        ash: '#0e0e14',
        slate: '#16161f',
        mist: '#1e1e2a',
        gold: '#c9a84c',
        'gold-bright': '#f0c866',
        crimson: '#8b1a1a',
        'crimson-bright': '#c0392b',
        'text-primary': '#e8e0d0',
        'text-muted': '#7a7368',
        'text-dim': '#4a4540',
        resonance: '#4a7fa5',
        fracture: '#7b4fa5',
      },
      fontFamily: {
        display: ['"Cinzel"', 'Georgia', 'serif'],
        body: ['"Source Serif 4"', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      backgroundImage: {
        'noise': "url('/noise.svg')",
      },
    },
  },
  plugins: [],
};
