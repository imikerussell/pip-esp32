# ESP-Mosaico drama_pet

Created with `python mosaico.py project init my_app`.
The same GSP 1.5.1 scene and portable C UI run on PC and ESP-Mosaico.

From the workspace root:

```sh
python mosaico.py project sim --project projects/drama_pet --interactive
python mosaico.py recover
python mosaico.py iris system-update --project projects/drama_pet
```

Run `recover` before the first install on a blank or unverified device.
Use `system-update` for new apps or changed resources/layouts. Use `app-update`
only for code changes with an identical full partition table and resources.

Edit `main/hello_ui.c` and `ui/main.json`. `main/board_display.c` declares the
application display policy. Vibe Mode, GSP bundle loading and screen capture are
shared optional components from esp-mosaico-utils. `pc/` contains the portable
backend; firmware dependencies are resolved with ESP-IDF before its first run.
