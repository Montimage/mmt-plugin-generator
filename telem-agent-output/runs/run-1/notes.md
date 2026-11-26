# Run 1

- validate: exit 0. generate: exit 0.
- build: exit 5, `build.missing-hook` at src/telem_impl.c (`telem_hook_extract_readings`).
- Fix: define the hook in src/telem_impl.c (the `readings` counter is not in the packet).
