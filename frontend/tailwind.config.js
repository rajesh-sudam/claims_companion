/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: "#0C0E1A",       // Dark navy background
        surface: "#1A1C29",          // Slightly lighter background for sections/cards
        textPrimary: "#FFFFFF",      // Main white text
        textSecondary: "#F0F0F0",    // Subtle gray text
        accent: {
          DEFAULT: "#8A5EFF",        // Bright purple accent
          hover: "#A685FF",          // Lighter purple hover state
        },
        border: "#2A2C3A",           // Border / divider gray
      },
    },
  },
  plugins: [],
};