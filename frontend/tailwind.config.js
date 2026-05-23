/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#f7f7fb",
        panel: "#ffffff",
        line: "#e4e4e7",
        accent: "#6d28d9",
        ink: "#18181b"
      },
      boxShadow: {
        sentinel: "0 16px 40px rgba(24, 24, 27, 0.08)"
      }
    }
  },
  plugins: []
};
