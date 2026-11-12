# hexnext-site

Public website for the Hex Next Android app, served by GitHub Pages.

- https://bingblop.github.io/hexnext-site/ — landing page
- https://bingblop.github.io/hexnext-site/privacy-policy.html — privacy policy (the URL used in Google Play Console)

The privacy policy source of record is `docs/site/privacy-policy.html` in the Hex-Next app repository; copy it here when it changes.

## downloads/

`HexNext-QS-Notifications-Module.apk` is the optional System UI module (Hex-Next `android/qstiles`).
Owner and beta builds of the app read `downloads/module.json` (`versionCode`, `versionName`,
`sha256`, `apk`) and install the APK only when its SHA-256 matches. Update both together.
