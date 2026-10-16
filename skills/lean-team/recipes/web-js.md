# Recipe: web / JavaScript projects

Read this file when the project is a web app (Node, Vite, browser UI). It turns the core's "verification = one command" into concrete web checks.

## One check command
- First build-out: create a single check command (e.g. `npm run check` = typecheck + lint + unit + headless e2e) and/or an in-app self-test (`?selftest=1` → `window.__selftest = {pass, failures}`) that plays the main flow end to end.
- Prefer pure-logic unit tests with fakes (fast, no browser). Headless e2e (Playwright with the system browser, `channel: 'msedge'|'chrome'`) instead of driving a visible browser by hand.
- **Make the check output tiny** (measured: 8.3k → 0.74k chars, −91%, per run, per agent): `eslint --quiet` (warnings via a separate `lint:all`), dot reporters for unit and e2e, Playwright `webServer.stdout/stderr: 'ignore'`, `npm run -s`.
- Add iteration scripts and tell builders to use them: `check:fast` (typecheck+lint+unit), `test:changed` (`vitest run --changed`), `e2e:changed` (`playwright test --only-changed=HEAD`); full `check` once at the end.
- Only one agent runs the production build (`vite build` empties a shared `dist/`); parallel agents typecheck only.
- Content-heavy projects: a written authoring guide + a `content:check` validator lets a cheap model author units (~80k haiku tokens per unit per language) with quality enforced by the check, not by an expensive reviewer.

## Browser specifics
- A frozen page (main-thread infinite loop) can't be debugged by reading code cheaply: reproduce it in Playwright, fire the action without awaiting, and if `page.evaluate` stops answering, `Debugger.pause` via a CDP session and print the top call frames — it names the spinning function and line. Keep it as a regression test.
- Browser panes may be hidden → `requestAnimationFrame` stops. Give the app a manual `step(dt)` / speed hook for tests, and tell builders to use it.
- After agents change UI layout, measure it yourself at a laptop size and a phone size (e.g. 1366×768 and 390×844): a Playwright script with the system browser reports `getBoundingClientRect()` of the key blocks and `scrollWidth − innerWidth` — near-zero image tokens. Agents without a browser miss short/narrow viewports. Keep 1–2 zoomed screenshots (`clip` + `deviceScaleFactor`) for what only eyes can judge.
- To drive app state from such a script, start a fresh dev server: after HMR, `import('/src/store.ts')` from the page can get a different module instance than the app's.
