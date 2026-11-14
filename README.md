# hexnext-site

Public website for the Hex Next Android app, served by GitHub Pages.

- https://bingblop.github.io/hexnext-site/ — landing page
- https://bingblop.github.io/hexnext-site/privacy-policy.html — privacy policy (the URL used in Google Play Console)

The privacy policy source of record is `docs/site/privacy-policy.html` in the Hex-Next app repository; copy it here when it changes.

## downloads/

`HexNext-QS-Notifications-Module.apk` is the optional System UI module (Hex-Next `android/qstiles`).
Owner and beta builds of the app read `downloads/module.json` (`versionCode`, `versionName`,
`sha256`, `apk`) and install the APK only when its SHA-256 matches. Update both together.

## Theme gallery

The theme section of `index.html` (the tab strip and its manifest, between `themes:begin` and
`themes:end`) and the pictures in `assets/themes/<id>/` are written by `tools/build_themes.py`
from the pack files; `assets/themes.js` draws the chosen pack. `tools/themes.json` lists the packs
in tab order. To refresh after packs change:

    python3 tools/build_themes.py --packs <folder with <id>.zip> --work <scratch folder>

Add `--only id,id` to redraw some packs. Only pictures and display names are copied to the site.
`assets/themes/galaxy/preview-002.webp` is the middle phone of the hero and is kept by hand.
