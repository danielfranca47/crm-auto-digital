import type { Config } from "tailwindcss";

export default {
	darkMode: ["class"],
	content: [
		"./pages/**/*.{ts,tsx}",
		"./components/**/*.{ts,tsx}",
		"./app/**/*.{ts,tsx}",
		"./src/**/*.{ts,tsx}",
	],
	prefix: "",
	theme: {
		container: {
			center: true,
			padding: '2rem',
			screens: {
				'2xl': '1400px'
			}
		},
		extend: {
			colors: {
				border: 'hsl(var(--border))',
				input: 'hsl(var(--input))',
				ring: 'hsl(var(--ring))',
				background: 'hsl(var(--background))',
				foreground: 'hsl(var(--foreground))',
				primary: {
					DEFAULT: 'hsl(var(--primary))',
					foreground: 'hsl(var(--primary-foreground))'
				},
				secondary: {
					DEFAULT: 'hsl(var(--secondary))',
					foreground: 'hsl(var(--secondary-foreground))'
				},
				destructive: {
					DEFAULT: 'hsl(var(--destructive))',
					foreground: 'hsl(var(--destructive-foreground))'
				},
				muted: {
					DEFAULT: 'hsl(var(--muted))',
					foreground: 'hsl(var(--muted-foreground))'
				},
				accent: {
					DEFAULT: 'hsl(var(--accent))',
					foreground: 'hsl(var(--accent-foreground))'
				},
				popover: {
					DEFAULT: 'hsl(var(--popover))',
					foreground: 'hsl(var(--popover-foreground))'
				},
				card: {
					DEFAULT: 'hsl(var(--card))',
					foreground: 'hsl(var(--card-foreground))'
				},
				// Orion Design System tokens
			'orion-bg':     'var(--o-bg)',
			'orion-s1':     'var(--o-s1)',
			'orion-s2':     'var(--o-s2)',
			'orion-s3':     'var(--o-s3)',
			'orion-text':   'var(--o-text)',
			'orion-sub':    'var(--o-sub)',
			'orion-dim':    'var(--o-dim)',
			'orion-active': 'var(--o-active)',
			'orion-warn':   'var(--o-warn)',
			'orion-hot':    'var(--o-hot)',
			'orion-cold':   'var(--o-cold)',
			'orion-purple': 'var(--o-purple)',
			// CRM Specific Colors
				'crm-header': 'hsl(var(--crm-header))',
				'crm-header-foreground': 'hsl(var(--crm-header-foreground))',
				'kanban-column': 'hsl(var(--kanban-column))',
				'kanban-column-header': 'hsl(var(--kanban-column-header))',
				'lead-card': 'hsl(var(--lead-card))',
				'lead-card-hover': 'hsl(var(--lead-card-hover))',
				'lead-card-border': 'hsl(var(--lead-card-border))',
				success: {
					DEFAULT: 'hsl(var(--success))',
					foreground: 'hsl(var(--success-foreground))'
				},
				warning: {
					DEFAULT: 'hsl(var(--warning))',
					foreground: 'hsl(var(--warning-foreground))'
				},
				info: {
					DEFAULT: 'hsl(var(--info))',
					foreground: 'hsl(var(--info-foreground))'
				}
			},
			fontFamily: {
				'orion-display': ['"Playfair Display"', 'Georgia', 'serif'],
				'orion-mono':    ['"DM Mono"', 'monospace'],
				'orion-serif':   ['Literata', 'Georgia', 'serif'],
			},
			borderRadius: {
				lg: 'var(--radius)',
				md: 'calc(var(--radius) - 2px)',
				sm: 'calc(var(--radius) - 4px)'
			},
			keyframes: {
				'accordion-down': {
					from: {
						height: '0'
					},
					to: {
						height: 'var(--radix-accordion-content-height)'
					}
				},
				'accordion-up': {
					from: {
						height: 'var(--radix-accordion-content-height)'
					},
					to: {
						height: '0'
					}
				}
			},
			animation: {
				'accordion-down': 'accordion-down 0.2s ease-out',
				'accordion-up': 'accordion-up 0.2s ease-out'
			}
		}
	},
	plugins: [require("tailwindcss-animate")],
} satisfies Config;
