/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        primary: '#0369A1',        // Cisco Commerce blue
        secondary: '#E0F2FE',      // Light blue for cards/aside
        accent: '#0284C7',         // Main button blue
        grayBg: '#F9FAFB',         // Main background
        border: '#E5E7EB',         // Default borders
        warning: '#FEF9C3',        // Warning status background
        warningText: '#854D0E',    // Warning text
        neutral: '#374151',        // Dark gray text
        light: '#9CA3AF',          // Light gray text
        dark: '#111827',           // Almost black text
        pink: '#F43F5E',           // Notification badge
      },
      borderRadius: {
        sm: '2px',
        md: '4px',
        lg: '8px',
        xl: '12px',
        full: '9999px',
      },
      boxShadow: {
        nav: '0px 1px 3px rgba(0,0,0,0.1), 0px 1px 2px -1px rgba(0,0,0,0.1)', // Navigation bar shadow
        card: '0px 4px 24px rgba(0,0,0,0.08)', // Card shadow
        button: '0px 2px 8px rgba(56,189,248,0.1)', // Button shadow
      },
      fontFamily: {
        segoe: ['Segoe UI Symbol', 'Inter', 'sans-serif'], // Main font
        awesome: ['Font Awesome 5 Free'], // Icon font
      },
    },
  },
  plugins: [],
}
