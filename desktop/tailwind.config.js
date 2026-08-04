/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{ts,tsx,html}'],
  theme: {
    extend: {
      colors: {
        // 古玉主题色系 — 温润内敛
        jade: {
          50:  '#f0f7f2',
          100: '#d9edde',
          200: '#b5d9bf',
          300: '#84bf94',
          400: '#5aa36b',
          500: '#3d8a4f',
          600: '#2d6f3c',
          700: '#255931',
          800: '#1f4728',
          900: '#1a3a22',
          950: '#0d2012',
        },
        // 暖玉色 — 羊脂白玉的暖调
        warm: {
          50:  '#fefce8',
          100: '#fef9c3',
          200: '#fef08a',
          300: '#fde047',
          400: '#facc15',
          500: '#eab308',
          600: '#ca8a04',
          700: '#a16207',
          800: '#854d0e',
          900: '#713f12',
          950: '#422006',
        },
        // 沁色 — 古玉受沁的铁锈红褐色
        patina: {
          50:  '#fdf8f6',
          100: '#f9ede8',
          200: '#f3d8ce',
          300: '#e9baa7',
          400: '#dc9477',
          500: '#ce7350',
          600: '#bb5a3a',
          700: '#9c4931',
          800: '#823d2c',
          900: '#6d3528',
          950: '#3a1913',
        },
        // 金石色 — 青铜器/古器物的厚重底色
        bronze: {
          50:  '#fafaf9',
          100: '#f0efec',
          200: '#dbd6ce',
          300: '#c1b8a9',
          400: '#a49882',
          500: '#8f826a',
          600: '#776b58',
          700: '#615548',
          800: '#52473e',
          900: '#473d37',
          950: '#28211d',
        },
      },
      fontFamily: {
        sans: [
          '"PingFang SC"', '"Microsoft YaHei"', '"Hiragino Sans GB"',
          '"Noto Sans SC"', 'system-ui', 'sans-serif',
        ],
        serif: [
          '"Noto Serif SC"', '"Source Han Serif SC"',
          '"STSong"', '"SimSun"', 'Georgia', 'serif',
        ],
      },
      borderRadius: {
        'jade': '0.5rem',
      },
      boxShadow: {
        'jade': '0 1px 3px rgba(61, 138, 79, 0.12), 0 1px 2px rgba(61, 138, 79, 0.08)',
        'jade-lg': '0 4px 16px rgba(61, 138, 79, 0.1), 0 2px 4px rgba(0,0,0,0.06)',
        'patina': '0 2px 8px rgba(187, 90, 58, 0.15)',
      },
      animation: {
        'pulse-soft': 'pulseSoft 3s ease-in-out infinite',
        'slide-up': 'slideUp 0.3s ease-out',
        'fade-in': 'fadeIn 0.4s ease-out',
      },
      keyframes: {
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.8' },
        },
        slideUp: {
          '0%': { transform: 'translateY(12px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
