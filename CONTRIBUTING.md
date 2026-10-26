# Contributing to Ember

Use Python 3.10+ and Node.js for development. No packages need to be installed.

1. Create a branch and edit `dist/` for UI changes or `bridge.py` for controller changes.
2. Run `python3 -m unittest -v test_bridge.py` and `node --check dist/app.js`.
3. Preview with `make preview` or the static server command in the README.
4. Check the interface at desktop and phone widths. Verify target adjustments, Auto/Manual/Off, pause/resume, unit conversion, and history controls.
5. For controller changes, add tests covering failure behavior as well as successful control. Use mocked sensor and XMRig responses for automated tests.

Never commit wallet credentials, real API tokens, `.env` files, or hardware logs containing secrets. Keep the bridge bound to loopback. Preserve pause-on-failure behavior when changing control logic.

The UI demo and hardware controller are separate runtime paths. A static UI change cannot directly access a user's local XMRig API. Pushes to main run checks and deploy dist/ to GitHub Pages through .github/workflows/pages.yml.
