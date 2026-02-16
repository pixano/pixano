/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const theme = {
  fontFamily: {
    sans: ["DM Sans", "sans-serif"],
    mono: ["JetBrains Mono", "monospace"],
  },
  colors: {
    border: "hsl(var(--border) / <alpha-value>)",
    input: "hsl(var(--input) / <alpha-value>)",
    ring: "hsl(var(--ring) / <alpha-value>)",
    background: "hsl(var(--background) / <alpha-value>)",
    foreground: "hsl(var(--foreground) / <alpha-value>)",
    primary: {
      DEFAULT: "hsl(var(--primary) / <alpha-value>)",
      foreground: "hsl(var(--primary-foreground) / <alpha-value>)",
      light: "hsl(var(--primary-light) / <alpha-value>)",
    },
    secondary: {
      DEFAULT: "hsl(var(--secondary) / <alpha-value>)",
      foreground: "hsl(var(--secondary-foreground) / <alpha-value>)",
    },
    destructive: {
      DEFAULT: "hsl(var(--destructive) / <alpha-value>)",
      foreground: "hsl(var(--destructive-foreground) / <alpha-value>)",
    },
    muted: {
      DEFAULT: "hsl(var(--muted) / <alpha-value>)",
      foreground: "hsl(var(--muted-foreground) / <alpha-value>)",
    },
    accent: {
      DEFAULT: "hsl(var(--accent) / <alpha-value>)",
      foreground: "hsl(var(--accent-foreground) / <alpha-value>)",
    },
    popover: {
      DEFAULT: "hsl(var(--popover) / <alpha-value>)",
      foreground: "hsl(var(--popover-foreground) / <alpha-value>)",
    },
    card: {
      DEFAULT: "hsl(var(--card) / <alpha-value>)",
      foreground: "hsl(var(--card-foreground) / <alpha-value>)",
    },
    surface: {
      1: "hsl(var(--surface-1) / <alpha-value>)",
      2: "hsl(var(--surface-2) / <alpha-value>)",
      3: "hsl(var(--surface-3) / <alpha-value>)",
    },
    canvas: "hsl(var(--canvas-bg) / <alpha-value>)",
    success: {
      DEFAULT: "hsl(var(--success) / <alpha-value>)",
      foreground: "hsl(var(--success-foreground) / <alpha-value>)",
    },
    warning: {
      DEFAULT: "hsl(var(--warning) / <alpha-value>)",
      foreground: "hsl(var(--warning-foreground) / <alpha-value>)",
    },
    info: {
      DEFAULT: "hsl(var(--info) / <alpha-value>)",
      foreground: "hsl(var(--info-foreground) / <alpha-value>)",
    },
  },
  borderRadius: {
    "2xl": "calc(var(--radius-xl) + 4px)",
    xl: "var(--radius-xl)",
    lg: "var(--radius-lg)",
    md: "var(--radius)",
    sm: "calc(var(--radius) - 2px)",
  },
  boxShadow: {
    glass: "0 0 0 1px rgba(255,255,255,0.05), 0 4px 24px rgba(0,0,0,0.12)",
    "glass-sm": "0 0 0 1px rgba(255,255,255,0.05), 0 2px 8px rgba(0,0,0,0.08)",
    "glass-lg": "0 0 0 1px rgba(255,255,255,0.05), 0 8px 40px rgba(0,0,0,0.16)",
    "inner-glow": "inset 0 1px 0 rgba(255,255,255,0.05)",
    "elevation-1": "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
    "elevation-2": "0 4px 8px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)",
    "elevation-3": "0 12px 24px rgba(0,0,0,0.12), 0 4px 8px rgba(0,0,0,0.06)",
  },
  backdropBlur: {
    glass: "16px",
    "glass-heavy": "24px",
  },
};
