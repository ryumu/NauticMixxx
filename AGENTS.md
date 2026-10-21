# Windows C++ compatibility

- Never use `near` or `far` as identifiers in shared C++ code, including tests. Windows headers define them as macros and MSVC may fail with C2059/C3409.
- Use explicit identifiers such as `nearArtistRow` and `farArtistRow`; do not disable system macros to conceal a collision.
- Preserve the preventive identifier check in `scripts/test-windows-installer-contract.py`. Run it before Windows compilation; the native build script and CI both invoke it.

# Linux desktop builds

- Keep the desktop shortcut on the stable `packaging/linux/desktop.py` launcher, which follows the latest published build across versions and build roots.
- Preserve `CMAKE_PROJECT_INCLUDE=packaging/linux/desktop-build.cmake` when reconfiguring a native Linux build. Its successful-build hook refreshes the staged executable and resources; do not leave the desktop on an older staged copy after a direct CMake build.
- Keep bundled controller updates and backups on launch while preserving user preferences, custom mapping names and the library database.
