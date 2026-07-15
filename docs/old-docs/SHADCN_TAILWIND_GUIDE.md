# Visentix MVP: shadcn CLI & Tailwind CSS Setup Guide

This guide explains how to standardize the Visentix React frontend project with a **shadcn UI project structure**, **Tailwind CSS**, and **TypeScript**. 

Currently, the codebase uses **TypeScript** natively but relies on a custom **Vanilla CSS** design system. Below are step-by-step instructions to convert or initialize the workspace to support shadcn and Tailwind CSS.

---

## 1. Prerequisites (TypeScript Setup)
The project already utilizes TypeScript (`tsconfig.json`, `tsconfig.app.json`, and Vite's TypeScript compiler options). If initializing TypeScript from scratch in a raw React project, you would run:
```bash
npm install -D typescript @types/react @types/react-dom @types/node vite
npx tsc --init
```
Our Vite project is fully ready for TypeScript.

---

## 2. Installing & Initializing Tailwind CSS

To integrate Tailwind CSS into our React app:

### Step A: Install Dependencies
Run the following command in the `web/` folder to install Tailwind CSS, its peer dependencies, and path mapping utilities:
```bash
npm install -D tailwindcss postcss autoprefixer
```

### Step B: Generate Configurations
Generate the PostCSS and Tailwind configuration files:
```bash
npx tailwindcss init -p
```
This creates two files: `tailwind.config.js` and `postcss.config.js`.

### Step C: Configure Tailwind Paths
Modify `web/tailwind.config.js` to scan our React and TSX files for utility classes:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Map existing Visentix brand colors
        navy: {
          DEFAULT: '#09234F',
          light: '#0d2d66',
        },
        teal: {
          DEFAULT: '#55C7B3',
          light: '#7DD9CA',
        },
        gold: {
          DEFAULT: '#C8A46A',
          light: '#E8C98A',
        },
      },
    },
  },
  plugins: [],
}
```

### Step D: Add Tailwind Directives to CSS
At the top of your global CSS file (`web/src/index.css`), prepend the Tailwind directives:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Rest of your custom CSS tokens and resets... */
```

---

## 3. Initializing shadcn CLI

shadcn is a collection of re-usable components that you copy and paste into your apps, rather than a packaged library.

### Step A: Configure Vite Path Alias (`@/*`)
shadcn CLI requires path aliases to correctly generate and import components.
1. In `web/tsconfig.app.json`, add path mapping:
   ```json
   {
     "compilerOptions": {
       // ...
       "baseUrl": ".",
       "paths": {
         "@/*": ["./src/*"]
       }
     }
   }
   ```
2. In `web/vite.config.ts`, install `@types/node` (if not present) and add the path resolver:
   ```typescript
   import path from "path"
   import react from "@vitejs/plugin-react"
   import { defineConfig } from "vite"

   export default defineConfig({
     plugins: [react()],
     resolve: {
       alias: {
         "@": path.resolve(__dirname, "./src"),
       },
     },
   })
   ```

### Step B: Run the shadcn CLI Init Script
Run the initialization CLI:
```bash
npx shadcn@latest init
```
During initialization, the CLI will ask several configuration questions:
1. **Style framework**: Choose `Tailwind CSS`.
2. **Global CSS file**: Enter `src/index.css`.
3. **Import alias for components**: Enter `@/components`.
4. **Import alias for utils**: Enter `@/lib/utils`.
5. **Tailwind CSS variables**: Choose `Yes` or `No` (Yes will generate standard Tailwind color variables).

This command creates a `components.json` configuration file at the root of the `web/` project.

---

## 4. Rationale: The Default Path `/components/ui`

When shadcn CLI is initialized, the standard default output folder for newly added primitives (buttons, dialogs, inputs) is:
`src/components/ui`

### Why creating and preserving this folder is critical:
1. **Systematic Separation of Concerns**: 
   - `components/ui/` contains **low-level, un-opinionated primitives** (e.g., a raw button, dialog, sheet, or tooltip).
   - `components/` contains **domain-specific components** (e.g., `AdvisorNote.tsx`, `LineageDrawer.tsx`, `MetallicShield.tsx`) which contain application logic, specific organization variables, or custom branding.
2. **Automated CLI Updates**: 
   When you run `npx shadcn@latest add button`, the CLI is programmed to write directly to `components/ui/button.tsx`. Modifying this destination path manually breaks CLI automation.
3. **Ecosystem Compatibility**: 
   Most copy-paste UI libraries (like Aceternity, Magic UI, and shadcn extensions) assume standard path routing (`@/components/ui/...`). Sticking to this default path makes integrating new UI components seamless.
