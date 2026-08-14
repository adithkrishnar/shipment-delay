---
name: SupplyIQ Intelligence System
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#464554'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#767586'
  outline-variant: '#c7c4d7'
  surface-tint: '#494bd6'
  primary: '#4648d4'
  on-primary: '#ffffff'
  primary-container: '#6063ee'
  on-primary-container: '#fffbff'
  inverse-primary: '#c0c1ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#904900'
  on-tertiary: '#ffffff'
  tertiary-container: '#b55d00'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e1e0ff'
  primary-fixed-dim: '#c0c1ff'
  on-primary-fixed: '#07006c'
  on-primary-fixed-variant: '#2f2ebe'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#ffdcc5'
  tertiary-fixed-dim: '#ffb783'
  on-tertiary-fixed: '#301400'
  on-tertiary-fixed-variant: '#703700'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  data-table:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  container-margin: 24px
  gutter: 16px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style
The design system is anchored in a **Corporate / Modern** aesthetic, specifically tailored for high-stakes B2B supply chain management. It prioritizes clarity, authority, and rapid data synthesis. The visual narrative balances a heavy enterprise foundation with a modern, agile interface that feels "intelligent" rather than "industrial."

The style utilizes a minimalist approach with an emphasis on high-contrast surfaces, thin structural borders, and purposeful whitespace. By avoiding decorative gradients and glassmorphism, the system ensures that the user's cognitive load is reserved entirely for analytical decision-making. The emotional response is one of controlled precision and absolute reliability.

## Colors
The palette is built on a foundation of "Supply Indigo" for primary actions and "Deep Navy" for structural components like sidebars and navigation. 

- **Primary & Neutral**: Indigo is used sparingly for focus and interaction. Slates and Navies provide the enterprise "weight" required for a professional tool.
- **Risk Palette**: This is the most critical functional element of the system. These colors must remain pure and consistent; do not use them for decorative purposes. They are reserved exclusively for status indicators, risk scores, and alert states.
- **Surface Strategy**: Use `#FFFFFF` for primary content cards and `#F8FAFC` for the main canvas to create a subtle layered effect without relying on heavy shadows.

## Typography
The system uses **Inter** for all primary UI elements due to its exceptional legibility in data-dense environments. For technical metadata, risk scores, and supply chain IDs, **JetBrains Mono** is introduced to provide a distinct "data-first" feel.

Tighten letter spacing on larger headlines to maintain a premium, editorial look. In tables and dashboards, favor the `body-md` and `data-table` roles to maximize information density without sacrificing readability.

## Layout & Spacing
This design system utilizes a **12-column fluid grid** for dashboard views, transitioning to a single-column stack on mobile. 

- **Density**: The spacing rhythm is based on a 4px scale. For analytical views, use "Compact" spacing (8px-12px internal padding). For marketing or landing pages, use "Spacious" (24px-32px).
- **Alignment**: Align all analytical widgets to the 16px gutter. 
- **Responsive Strategy**: On tablet (768px+), sidebars should collapse into icons. On mobile (375px+), horizontal scrolling is permitted only for data tables; all other content must reflow vertically.

## Elevation & Depth
Depth is conveyed through **Tonal Layering** and **Low-Contrast Outlines**. 

- **Level 0 (Canvas)**: `#F8FAFC` background.
- **Level 1 (Cards)**: White background with a 1px border (`#E2E8F0`) and a very soft, diffused shadow (0px 4px 6px rgba(15, 23, 42, 0.05)).
- **Level 2 (Modals/Popovers)**: White background with a slightly more pronounced shadow and a darker border (`#334155`) to command focus.

Avoid heavy black shadows; instead, use shadows tinted with the primary navy (`#0F172A`) at very low opacities to maintain a clean, high-end feel.

## Shapes
The shape language is "Professional-Rounded." 

Cards and large containers use a 12px-16px radius (`rounded-lg` or `rounded-xl`) to soften the data-heavy interface. Smaller components like buttons, input fields, and tags use an 8px radius (`rounded-md`). This creates a hierarchy where the container feels like a modern frame, and the interactive elements inside feel precise and tactile.

## Components
- **Buttons**: Primary buttons use "Supply Indigo" with white text. Secondary buttons use a slate border with no fill. All buttons use 14px medium-weight text.
- **Risk Chips**: Small, pill-shaped indicators using the semantic risk palette. Text should be high-contrast (e.g., White text on Deep Red for Critical; Dark Green text on light green background for Low).
- **Data Tables**: Use alternating row highlights or subtle 1px horizontal dividers. Header text should be all-caps using the `label-sm` role.
- **Cards**: Every card must have a consistent 16px or 24px internal padding. Card headers should include a 1px bottom border.
- **Input Fields**: 1px border (`#E2E8F0`) that transitions to "Intelligence Blue" (`#3B82F6`) on focus. Use "JetBrains Mono" for numeric input values.
- **Charts**: Use thin stroke weights (1.5px - 2px) for line charts. Use the brand Indigo as the "Current/Actual" line and Slate for "Baseline/Forecast" lines.