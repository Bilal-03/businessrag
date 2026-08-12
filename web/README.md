# React + Vite

## Browser smoke tests

The critical authenticated workspace flows are covered with Playwright. The
tests use deterministic Supabase and API route fixtures, so they never need
production credentials or mutate production data.

```bash
npm install
npx playwright install chromium
npm run test:e2e
```

Use `npm run test:e2e:debug` to step through a failing test or
`npm run test:e2e:ui` for the Playwright UI runner. CI runs the same suite on
every push and pull request targeting `main`.

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and Oxlint's TypeScript related rules in your project.
