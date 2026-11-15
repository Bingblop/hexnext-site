#!/system/bin/sh
# Hex Next: One UI compatibility test for volunteer testers (One UI 7 and One UI 8, root required).
#
# What it does
#   Reads technical facts about this phone's Samsung system apps (resource tables, Samsung's own
#   colour palette overlays, System UI class names), copies Hex Next's own scan and apply logs when
#   the app is installed, takes a few screenshots of system screens in light and dark mode, and
#   packs everything into ONE file in the Downloads folder.
#
# What it changes
#   Nothing for good. Dark mode is switched once and switched back. Nothing is installed, removed
#   or themed, and nothing is sent anywhere: the result is a file the tester sends by hand.
#
# What it never reads
#   Photos, messages, contacts, accounts, passwords, notifications, or the list of installed apps.
#
# How a tester runs it (Termux, one line):
#   curl -fsSL https://bingblop.github.io/hexnext-site/oneui-test.sh -o t.sh && su -c "sh $PWD/t.sh"
#
# Switches for developers (environment):
#   HEXNEXT_NOSHOTS=1   no screenshots and no dark mode switch
#   HEXNEXT_NOXML=1     no colour and drawable XML files (a much smaller result)
#   HEXNEXT_OUT=/dir    where the result file goes (default: the Downloads folder)
#
# Written for /system/bin/sh (mksh) and the tools every Android 15+ phone has. Keep it that way:
# no bash, no Termux packages.

SCRIPT_VERSION=2

PATH=/system/bin:/system/xbin:/vendor/bin:/apex/com.android.art/bin:$PATH
export PATH
unset LD_PRELOAD LD_LIBRARY_PATH 2>/dev/null
umask 077

say() { printf '%s\n' "$*"; }
rule() { say "=================================================="; }

# ---------------------------------------------------------------- root
if [ "$(id -u 2>/dev/null)" != "0" ]; then
  case "$0" in /*) self=$0 ;; *) self=$PWD/$0 ;; esac
  if [ -f "$self" ] && command -v su >/dev/null 2>&1; then
    exec su -c "sh '$self'"
  fi
  rule
  say " This test needs root, and it did not get root."
  say ""
  say " 1. Open your root app (KernelSU, Magisk or APatch)."
  say " 2. Allow root for Termux:"
  say "    KernelSU / APatch: tap Superuser, tap Termux, turn the switch on."
  say "    Magisk: tap Superuser, turn the switch next to Termux on."
  say " 3. Come back here and paste the same command again."
  rule
  exit 1
fi

# ---------------------------------------------------------------- work folder
STAMP=$(date +%Y%m%d-%H%M%S)
W=
for base in /data/local/tmp /data; do
  [ -d "$base" ] || continue
  cand=$base/hexnext-test-$STAMP-$$
  if mkdir "$cand" 2>/dev/null; then W=$cand; break; fi
done
if [ -z "$W" ]; then
  say "Could not create a work folder on this phone. Nothing was changed."
  exit 1
fi
R=$W/hexnext-test
mkdir -p "$R"

ORIG_NIGHT=
KEEP_PID=
CLEANED=
cleanup() {
  [ -n "$CLEANED" ] && return
  CLEANED=1
  [ -n "$KEEP_PID" ] && kill "$KEEP_PID" 2>/dev/null
  [ -n "$ORIG_NIGHT" ] && cmd uimode night "$ORIG_NIGHT" >/dev/null 2>&1
  rm -rf "$W"
}
trap 'cleanup' EXIT
trap 'cleanup; exit 130' INT TERM HUP

if command -v timeout >/dev/null 2>&1; then TO=timeout; else TO=; fi
# t <seconds> <command...>: a command that may hang never stops the test.
t() { if [ -n "$TO" ]; then "$TO" "$@"; else shift; "$@"; fi; }
sec() { printf '\n===== %s =====\n' "$1"; }
clean() { printf '%s' "$1" | tr -c 'A-Za-z0-9._-' '_'; }

STEPS=6
STEP=0
step() { STEP=$((STEP + 1)); printf '\n[%s/%s] %s\n' "$STEP" "$STEPS" "$1"; }

# ---------------------------------------------------------------- what phone is this
ONEUI_RAW=$(getprop ro.build.version.oneui 2>/dev/null)
case "$ONEUI_RAW" in
  ''|*[!0-9]*) ONEUI=unknown ;;
  *) ONEUI="$((ONEUI_RAW / 10000)).$(((ONEUI_RAW % 10000) / 100))" ;;
esac
MODEL=$(getprop ro.product.model 2>/dev/null)
[ -n "$MODEL" ] || MODEL=phone
ANDROID=$(getprop ro.build.version.release 2>/dev/null)

# Start on an empty window, so the first picture shows this test and nothing typed before it.
[ -t 1 ] && printf '\033[3J\033[2J\033[H'
rule
say " Hex Next: One UI test (version $SCRIPT_VERSION)"
say " Phone: $MODEL, One UI $ONEUI, Android $ANDROID"
say ""
say " This takes 5 to 10 minutes."
say " The screen stays on and changes by itself."
say " PUT THE PHONE DOWN AND DO NOT TOUCH IT"
say " until this window comes back and says DONE."
rule

# A key press that does nothing, every few seconds, so the screen stays on and the phone does not
# go to sleep in the middle of the test. It stops by itself when this test ends or is stopped,
# and after 15 minutes at the latest.
(
  i=0
  while [ -d "$W" ] && kill -0 $$ 2>/dev/null && [ "$i" -lt 130 ]; do
    input keyevent 59 >/dev/null 2>&1
    sleep 7
    i=$((i + 1))
  done
) &
KEEP_PID=$!
sleep 6

# Which Hex Next build is installed (beta first: it is the one testers have).
HN=
HN_ALL=
for p in com.hexnext.themer.beta com.hexnext.themer com.hexnext.themer.owner; do
  if pm path "$p" 2>/dev/null | grep -q '^package:'; then
    HN_ALL="$HN_ALL $p"
    [ -n "$HN" ] || HN=$p
  fi
done

# ---------------------------------------------------------------- 1. the phone
step "Reading the phone's version"
{
  say "script_version=$SCRIPT_VERSION"
  say "date=$(date)"
  for p in ro.build.version.oneui ro.build.version.sem ro.build.version.sep \
    ro.build.version.release ro.build.version.sdk ro.build.version.security_patch \
    ro.build.display.id ro.build.PDA ro.build.type ro.build.tags ro.build.characteristics \
    ro.product.model ro.product.device ro.product.name ro.product.brand ro.product.manufacturer \
    ro.product.cpu.abi ro.csc.sales_code ro.csc.country_code ro.sf.lcd_density \
    ro.boot.verifiedbootstate ro.boot.flash.locked ro.boot.vbmeta.device_state ro.boot.warranty_bit \
    persist.sys.locale ro.product.locale; do
    printf '%s=%s\n' "$p" "$(getprop "$p" 2>/dev/null)"
  done
  sec "id"; id
  sec "kernel"; uname -r
  sec "selinux"; getenforce 2>&1
  sec "display"; t 10 wm size 2>&1; t 10 wm density 2>&1
  sec "night mode"; t 10 cmd uimode night 2>&1
  sec "root"
  for d in /data/adb/ksu /data/adb/ksud /data/adb/magisk /data/adb/ap /data/adb/apd /data/adb/lspd /data/adb/modules; do
    [ -e "$d" ] && say "present: $d"
  done
  t 10 su -v 2>&1 | head -2
  t 10 su -V 2>&1 | head -2
  sec "root modules (folder names only)"; ls /data/adb/modules 2>&1
  sec "Shizuku"; pidof shizuku_server 2>&1; pm path moe.shizuku.privileged.api 2>&1
  sec "Hex Next builds installed"; say "${HN_ALL:- none}"
  sec "free space (KB)"; df -k /data 2>&1 | tail -1
} >"$R/device.txt" 2>&1

{
  for k in accessibility_reduce_transparency wallpapertheme_state wallpapertheme_color \
    wallpapertheme_color_isgray lock_adaptive_color current_sec_active_themepackage \
    display_night_theme; do
    printf 'system %s=%s\n' "$k" "$(t 10 settings get system "$k" 2>&1)"
  done
  for k in theme_customization_overlay_packages ui_night_mode navigation_mode; do
    printf 'secure %s=%s\n' "$k" "$(t 10 settings get secure "$k" 2>&1)"
  done
  sec "system settings with theme, palette or colour in the name"
  t 15 settings list system 2>/dev/null | grep -i -E 'wallpapertheme|colortheme|color_theme|palette|themepackage'
  sec "Quick panel tiles (Samsung and Android ones only)"
  # A tile another app added would say which apps are installed, so those are left out.
  tiles=$(t 10 settings get secure sysui_qs_tiles 2>/dev/null | tr ',' '\n')
  printf '%s\n' "$tiles" | grep -v '^custom('
  printf '%s\n' "$tiles" | grep -E '^custom\((com\.samsung\.|com\.sec\.|com\.android\.|com\.dolby\.|com\.google\.)'
} >"$R/settings.txt" 2>&1

# ---------------------------------------------------------------- 2. overlays
step "Reading the theme overlays that are on right now"
t 40 cmd overlay list --user current >"$R/overlay-list.txt" 2>&1
SEMWT_ON=$(grep -c -E '^\[x\].*SemWT_' "$R/overlay-list.txt" 2>/dev/null)
SEMWT_ALL=$(grep -c -E 'SemWT_' "$R/overlay-list.txt" 2>/dev/null)
HN_OVERLAYS_ON=$(grep -c -i -E '^\[x\].*hexnext' "$R/overlay-list.txt" 2>/dev/null)
HN_OVERLAYS_ALL=$(grep -c -i -E 'hexnext' "$R/overlay-list.txt" 2>/dev/null)
: "${SEMWT_ON:=0}" "${SEMWT_ALL:=0}" "${HN_OVERLAYS_ON:=0}" "${HN_OVERLAYS_ALL:=0}"

mkdir -p "$R/overlay-dump"
grep -i -E 'hexnext|SemWT_|themedesigner|monet' "$R/overlay-list.txt" 2>/dev/null |
  sed -e 's/^\[[ x]\] //' -e 's/^--- //' -e 's/^ *//' | head -400 |
  while read -r id; do
    [ -n "$id" ] || continue
    t 15 cmd overlay dump "$id" >"$R/overlay-dump/$(clean "$id").txt" 2>&1
  done

ls -laZ /data/resource-cache/ >"$R/resource-cache.txt" 2>&1
{ sec "/data/overlays"; ls -laR /data/overlays 2>&1 | head -400; } >>"$R/resource-cache.txt"
mkdir -p "$R/frro"
for f in /data/resource-cache/*.frro; do
  [ -f "$f" ] || continue
  size=$(wc -c <"$f" 2>/dev/null | tr -d ' ')
  case "$size" in ''|*[!0-9]*) continue ;; esac
  # Samsung's palette overlays are a few KB; a Hex Next overlay with pictures can be far bigger.
  [ "$size" -le 4000000 ] && cp "$f" "$R/frro/" 2>/dev/null
done

# ---------------------------------------------------------------- 3. screenshots
shot_n=0
MODE=asfound
shot() {
  shot_n=$((shot_n + 1))
  f="$R/screens/$(printf '%02d' "$shot_n")-$1-$MODE"
  t 20 screencap -p "$f.png" 2>/dev/null
  rm -f "$W/ui.xml"
  t 20 uiautomator dump "$W/ui.xml" >/dev/null 2>&1
  [ -s "$W/ui.xml" ] && cp "$W/ui.xml" "$f.xml"
}
# tap_enabled_text <text>: taps a visible, enabled control with exactly that text. English only;
# on a phone in another language it finds nothing and the step is skipped.
tap_enabled_text() {
  [ -s "$W/ui.xml" ] || return 1
  b=$(grep -o -E "text=\"$1\"[^>]*enabled=\"true\"[^>]*bounds=\"\[[0-9]+,[0-9]+\]\[[0-9]+,[0-9]+\]\"" "$W/ui.xml" | head -1 |
    sed -n 's/.*bounds="\[\([0-9]*\),\([0-9]*\)\]\[\([0-9]*\),\([0-9]*\)\]".*/\1 \2 \3 \4/p')
  # shellcheck disable=SC2086
  set -- $b
  [ $# -eq 4 ] || return 1
  input tap $((($1 + $3) / 2)) $((($2 + $4) / 2))
}
night_word() { t 10 cmd uimode night 2>/dev/null | sed -n 's/.*: *//p' | head -1; }
shots_for_mode() {
  MODE=$1
  t 10 cmd statusbar expand-settings >/dev/null 2>&1; sleep 3; shot quickpanel
  t 10 cmd statusbar collapse >/dev/null 2>&1; sleep 1
  t 20 am start -W -a android.settings.DISPLAY_SETTINGS >/dev/null 2>&1; sleep 3; shot display
  t 20 am start -W -a android.settings.SOUND_SETTINGS >/dev/null 2>&1; sleep 3; shot sound
  if [ -n "$HN" ]; then
    t 20 am start -W -a android.settings.APPLICATION_DETAILS_SETTINGS -d "package:$HN" >/dev/null 2>&1
    sleep 3; shot appinfo
    # The confirmation box of "Force stop" is a system popup box. It is only looked at: Back
    # closes it, so nothing is stopped.
    if tap_enabled_text 'Force stop'; then
      sleep 2; shot popup
      input keyevent KEYCODE_BACK; sleep 1
    fi
  fi
  t 20 am start -W -a android.intent.action.DIAL -d tel: >/dev/null 2>&1; sleep 3; shot dialer
  input keyevent KEYCODE_BACK; sleep 1
  # Shows the volume slider without changing the volume.
  t 10 cmd media_session volume --show --stream 3 --adj same >/dev/null 2>&1; sleep 1; shot volume
  sleep 3
  input keyevent KEYCODE_HOME; sleep 1
}

if [ -z "${HEXNEXT_NOSHOTS:-}" ]; then
  step "Taking pictures of system screens (light and dark). Do not touch the phone."
  mkdir -p "$R/screens"
  TOP=$(t 15 dumpsys activity activities 2>/dev/null | grep -E 'topResumedActivity|mResumedActivity' | head -1 |
    sed -n 's/.* u[0-9]* \([^ }]*\).*/\1/p')
  NIGHT=$(night_word)
  case "$NIGHT" in
    yes) NOW=dark ;;
    no) NOW=light ;;
    *) if t 15 dumpsys uimode 2>/dev/null | grep -q 'mComputedNightMode=true'; then NOW=dark; else NOW=light; fi ;;
  esac
  # The terminal with the keyboard up: the only screen that shows Samsung Keyboard.
  MODE=$NOW; shot terminal
  shots_for_mode "$NOW"
  case "$NIGHT" in
    yes|no|auto|custom_schedule|custom_bedtime)
      ORIG_NIGHT=$NIGHT
      if [ "$NOW" = dark ]; then OTHER=light; t 10 cmd uimode night no >/dev/null 2>&1
      else OTHER=dark; t 10 cmd uimode night yes >/dev/null 2>&1; fi
      # Samsung rebuilds its palette overlays after the switch and Hex Next answers; wait for both.
      sleep 25
      [ -n "$TOP" ] && t 15 am start -n "$TOP" >/dev/null 2>&1
      sleep 3; MODE=$OTHER; shot terminal
      shots_for_mode "$OTHER"
      t 10 cmd uimode night "$ORIG_NIGHT" >/dev/null 2>&1
      ORIG_NIGHT=
      sleep 2
      ;;
  esac
  [ -n "$TOP" ] && t 15 am start -n "$TOP" >/dev/null 2>&1
  say "    Pictures taken: $shot_n. The rest needs no screen changes; please wait for DONE."
else
  step "Screenshots skipped"
fi

# ---------------------------------------------------------------- 4. system apps
step "Reading the system apps' resource tables (the slow part, about 2 minutes)"
TARGETS="android com.android.systemui com.android.settings com.sec.android.app.launcher
com.samsung.android.honeyboard com.samsung.android.dialer com.samsung.android.incallui
com.samsung.android.app.contacts com.sec.android.app.myfiles com.sec.android.gallery3d
com.sec.android.app.clockpackage com.sec.android.app.popupcalculator com.samsung.android.calendar
com.samsung.android.lool com.samsung.android.app.aodservice com.samsung.android.app.smartcapture
com.samsung.android.app.notes com.samsung.android.app.reminder com.sec.android.app.sbrowser
com.samsung.android.email.provider com.sec.android.app.music com.sec.android.app.voicenote
com.sec.android.app.shealth com.android.settings.intelligence com.samsung.android.app.telephonyui
com.samsung.android.smartsuggestions com.samsung.android.forest com.samsung.android.rubin.app
com.samsung.android.app.routines com.sec.android.app.soundalive com.samsung.android.service.aircommand
com.sec.hearingadjust com.samsung.android.smartmirroring com.samsung.android.secsoundpicker
com.samsung.android.app.soundpicker com.samsung.android.bixby.agent com.samsung.android.app.interpreter
com.samsung.android.app.dressroom com.sec.unifiedwfc com.sec.android.mimage.photoretouching
com.samsung.android.warrantycare com.samsung.android.themestore com.samsung.android.setting.multisound
com.samsung.android.mdecservice com.samsung.android.inputshare com.samsung.android.hwresourceshare
com.samsung.android.hwresourceshare.storage com.samsung.android.game.gametools
com.samsung.android.da.daagent com.samsung.android.app.sketchbook com.samsung.android.app.sharelive
com.wssyncmldm com.samsung.accessibility com.samsung.android.biometrics.app.setting
com.samsung.android.privacydashboard com.samsung.android.callassistant com.sec.android.app.camera
com.samsung.android.app.cameraassistant com.sec.android.daemonapp
com.samsung.android.scloud com.samsung.android.accessibility.talkback com.samsung.accessory.budsunitemgr
com.samsung.android.dynamiclock com.samsung.android.samsungpassautofill com.samsung.android.service.tagservice
com.samsung.android.service.airviewdictionary com.samsung.android.mcfds com.samsung.android.video
com.samsung.app.newtrim com.samsung.android.visionintelligence com.samsung.android.app.galaxyraw
com.samsung.android.messaging com.samsung.android.app.galaxyfinder com.samsung.android.themecenter
com.samsung.systemui.navillera com.samsung.android.goodlock com.samsung.android.themedesigner"

UNZIP=
for c in unzip /system/bin/unzip /data/adb/magisk/busybox /data/adb/ksu/bin/busybox /data/adb/ap/bin/busybox; do
  if command -v "$c" >/dev/null 2>&1; then
    case "$c" in *busybox) UNZIP="$c unzip" ;; *) UNZIP=$c ;; esac
    break
  fi
done
FREE_KB=$(df -k /data 2>/dev/null | tail -1 | sed -n 's/^[^ ]* *[0-9]* *[0-9]* *\([0-9]*\).*/\1/p')
case "$FREE_KB" in ''|*[!0-9]*) FREE_KB=9999999 ;; esac
XML=1
[ -n "${HEXNEXT_NOXML:-}" ] && XML=
[ "$FREE_KB" -lt 600000 ] && XML=
# The XML files are many small ones: about 300 MB on the phone for all apps, a tenth of that
# once packed. A phone that is short of space gets the most important apps only.
XML_CAP_KB=250000
[ "$FREE_KB" -gt 3000000 ] && XML_CAP_KB=700000
XML_NOTE=

mkdir -p "$R/arsc" "$R/filelist" "$R/xml"
printf 'package\tapk\tversionName\tversionCode\tarsc_bytes\tsplits\n' >"$R/packages.txt"
count=0
found=0
for pkg in $TARGETS; do
  count=$((count + 1))
  [ $((count % 15)) -eq 0 ] && say "    $count apps checked..."
  paths=$(t 15 pm path "$pkg" 2>/dev/null | sed -n 's/^package://p')
  apk=$(printf '%s\n' "$paths" | head -1)
  if [ -z "$apk" ] || [ ! -f "$apk" ]; then
    printf '%s\tNOT INSTALLED\t\t\t\t\n' "$pkg" >>"$R/packages.txt"
    continue
  fi
  found=$((found + 1))
  splits=$(printf '%s\n' "$paths" | grep -c .)
  info=$(t 15 dumpsys package "$pkg" 2>/dev/null | grep -E 'versionName=|versionCode=' | head -2 | tr -s ' \n' '  ')
  vname=$(printf '%s' "$info" | sed -n 's/.*versionName=\([^ ]*\).*/\1/p')
  vcode=$(printf '%s' "$info" | sed -n 's/.*versionCode=\([0-9]*\).*/\1/p')
  bytes=0
  if [ -n "$UNZIP" ]; then
    # shellcheck disable=SC2086
    $UNZIP -p "$apk" resources.arsc >"$R/arsc/$pkg.arsc" 2>/dev/null
    bytes=$(wc -c <"$R/arsc/$pkg.arsc" 2>/dev/null | tr -d ' ')
    [ "${bytes:-0}" -gt 0 ] 2>/dev/null || rm -f "$R/arsc/$pkg.arsc"
    # shellcheck disable=SC2086
    $UNZIP -l "$apk" >"$R/filelist/$pkg.txt" 2>/dev/null
    if [ -n "$XML" ]; then
      mkdir -p "$R/xml/$pkg"
      # shellcheck disable=SC2086
      $UNZIP -q -o -d "$R/xml/$pkg" "$apk" 'res/color*/*' 'res/drawable*/*.xml' >/dev/null 2>&1
      if [ ! -d "$R/xml/$pkg/res" ]; then
        # An app built with short resource paths (res/aB.xml) has no such folders: take its XML.
        # shellcheck disable=SC2086
        $UNZIP -q -o -d "$R/xml/$pkg" "$apk" 'res/*.xml' >/dev/null 2>&1
      fi
      used=$(du -sk "$R/xml" 2>/dev/null | sed -n 's/^\([0-9]*\).*/\1/p')
      if [ "${used:-0}" -gt "$XML_CAP_KB" ] 2>/dev/null; then
        XML=
        XML_NOTE="stopped after $pkg: the XML files passed $((XML_CAP_KB / 1000)) MB"
      fi
    fi
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$pkg" "$apk" "$vname" "$vcode" "${bytes:-0}" "$splits" >>"$R/packages.txt"
done
say "    $found of $count apps are on this phone."

# System UI class names, for the optional System UI module (which class draws what differs
# between One UI versions).
SYSUI=$(t 15 pm path com.android.systemui 2>/dev/null | sed -n 's/^package://p' | head -1)
if [ -n "$UNZIP" ] && [ -n "$SYSUI" ]; then
  # shellcheck disable=SC2086
  $UNZIP -p "$SYSUI" 'classes*.dex' 2>/dev/null | tr '\000' '\n' |
    grep -a -o -E 'Lcom/(android/systemui|android/compose|samsung)/[A-Za-z0-9_/$]+;' |
    sort -u >"$R/systemui-classes.txt" 2>/dev/null
  DEXLIST=
  for c in dexlist /apex/com.android.art/bin/dexlist; do
    command -v "$c" >/dev/null 2>&1 && { DEXLIST=$c; break; }
  done
  if [ -n "$DEXLIST" ]; then
    t 180 "$DEXLIST" "$SYSUI" 2>/dev/null |
      grep -E 'DarkIconDispatcher|NotificationBackgroundView|BrightnessLottie|EmptyMediaPlayer|DrawablePainter|QSTileViewImpl|QSIconViewImpl|SecQSTile|QSTileImpl|BrightnessSlider|VolumePanel|SecVolume' |
      head -c 8000000 >"$R/systemui-methods.txt" 2>/dev/null
  fi
  # Names only (--list). The full dump holds notification keys, recently used apps, the song that
  # is playing, Bluetooth and Wi-Fi names; the filter keeps one-word lines in case --list is ignored.
  t 30 dumpsys activity service com.android.systemui/.SystemUIService dumpables --list 2>/dev/null |
    grep -E '^[A-Za-z0-9_.$:/-]+$' | head -3000 >"$R/systemui-dumpables.txt"
fi

# ---------------------------------------------------------------- 5. Hex Next's own files
step "Copying Hex Next's own scan and apply logs"
APPLY_SEEN=
SCAN_SEEN=
for pkg in $HN_ALL; do
  A=/data/data/$pkg/files
  D=$R/app/$pkg
  mkdir -p "$D/logs"
  t 15 dumpsys package "$pkg" 2>/dev/null | grep -E 'versionName=|versionCode=|firstInstallTime=|lastUpdateTime=' | head -4 >"$D/version.txt"
  { ls -la "$A" 2>&1; for d in reports logs scan requests activity; do sec "$d"; ls -laR "$A/$d" 2>&1 | head -600; done; } >"$D/files-list.txt"
  mkdir -p "$D/reports"
  for f in "$A"/reports/*.json "$A"/reports/*.txt; do
    [ -f "$f" ] || continue
    head -c 12000000 "$f" >"$D/reports/${f##*/}" 2>/dev/null
  done
  [ -f "$A/reports/apply-last.json" ] && APPLY_SEEN=1
  ls "$A"/reports/2*.json >/dev/null 2>&1 && SCAN_SEEN=1
  for f in $(ls -t "$A"/logs/*.jsonl 2>/dev/null | head -5); do
    head -c 8000000 "$f" >"$D/logs/${f##*/}" 2>/dev/null
  done
  [ -f "$A/theme.json" ] && head -c 2000000 "$A/theme.json" >"$D/theme.json"
  [ -f "$A/activity/activity.log" ] && head -c 4000000 "$A/activity/activity.log" >"$D/activity.log"
  [ -d "$A/requests" ] && cp -r "$A/requests" "$D/requests" 2>/dev/null
  [ -d "$A/scan/semwt" ] && cp -r "$A/scan/semwt" "$D/scan-semwt" 2>/dev/null
done

# What a handful of well-known colours resolve to right now (the theme's value, Samsung's palette
# value, or the stock one).
lookup() { printf '%s %s -> %s\n' "$1" "$2" "$(t 10 cmd overlay lookup --user current "$1" "$1:$2" 2>&1 | head -1)"; }
{
  for n in color/system_accent1_100 color/system_accent1_500 color/system_accent1_600 color/system_neutral1_50 \
    color/system_neutral1_900 color/sesl_primary_color_light color/sesl_primary_color_dark \
    color/sesl_switch_track_on_color_light color/sesl_switch_track_on_color_dark \
    color/sesl_control_activated_color_light color/sesl_control_activated_color_dark \
    color/sesl_round_and_bgcolor_light color/sesl_round_and_bgcolor_dark \
    color/sesl_dialog_background_color_light color/sesl_dialog_background_color_dark; do
    lookup android "$n"
  done
  for n in color/sec_widget_round_and_bgcolor color/sesl_primary_color_light color/sesl_primary_color_dark \
    color/sesl_switch_track_on_color_light color/sesl_switch_track_on_color_dark \
    color/sesl_round_and_bgcolor_light color/sesl_round_and_bgcolor_dark \
    color/sec_settings_background_color drawable/sec_ic_settings_display drawable/sec_ic_settings_sound; do
    lookup com.android.settings "$n"
  done
  for n in color/qs_tile_round_background_on color/qs_tile_round_background_dim color/qs_tile_container_bg \
    color/qs_tile_label color/qs_tile_sub_label color/qs_tile_icon_off_tint_color \
    color/qs_tile_container_bg_border_color color/sec_panel_background_color \
    bool/theme_status_bar_icon_color; do
    lookup com.android.systemui "$n"
  done
  # The first names Hex Next itself asked for, per app, when the app kept its requests.
  for pkg in $HN_ALL; do
    for f in /data/data/"$pkg"/files/requests/*.json; do
      [ -f "$f" ] || continue
      target=${f##*/}; target=${target%.json}
      for n in $(grep -o -E '(color|bool|dimen|integer)/[A-Za-z0-9_.]+' "$f" 2>/dev/null | sort -u | head -12); do
        lookup "$target" "$n"
      done
    done
  done
} >"$R/lookups.txt" 2>&1

# Crashes and overlay messages only; never the whole log.
{
  sec "crash buffer: System UI, system server and Hex Next"
  # Only the lines of those processes, found by the PID that logged the crash: the buffer holds
  # other apps' crashes too, and their names would say which apps are installed.
  t 30 logcat -d -b crash -v threadtime >"$W/crash.txt" 2>/dev/null
  CRASH_PIDS=$(grep -E 'Process: (com\.android\.systemui|system_server|com\.hexnext\.[A-Za-z0-9_.]+), PID: |FATAL EXCEPTION IN SYSTEM PROCESS|>>> (com\.android\.systemui|system_server|com\.hexnext\.[A-Za-z0-9_.]+) <<<' "$W/crash.txt" 2>/dev/null |
    sed -n 's/^[0-9-]* [0-9:.]* *\([0-9][0-9]*\) .*/\1/p' | sort -u)
  for p in $CRASH_PIDS; do
    grep -E "^[0-9-]+ [0-9:.]+ +$p +[0-9]+ " "$W/crash.txt" 2>/dev/null
  done | sort | tail -400
  rm -f "$W/crash.txt"
  sec "overlay and Hex Next lines"
  t 30 logcat -d 2>/dev/null | grep -i -E 'OverlayManager|idmap2|FabricatedOverlay|HexNext|ThemeService|ThemeApplier|FrroWriter' | tail -400
} >"$R/logcat.txt" 2>&1

# ---------------------------------------------------------------- 6. pack
step "Packing everything into one file"
NOTES=
note() { NOTES="$NOTES
 * $1"; }
if [ -z "$HN" ]; then
  note "Hex Next is not installed on this phone yet. Do PART 2 of the instructions, then paste the command again."
elif [ -z "$APPLY_SEEN" ] || [ "$HN_OVERLAYS_ON" -eq 0 ] 2>/dev/null; then
  note "No Hex Next theme is on right now. Open Hex Next, tap \"Apply theme\", wait for \"Theme applied\", then paste the command again."
fi
if [ "$SEMWT_ON" -eq 0 ] 2>/dev/null; then
  note "The Samsung colour palette is off. Do step 1 of PART 1 of the instructions (Settings > Wallpaper and style > Color palette), wait one minute, then paste the command again."
fi
{
  say "Hex Next One UI test, script version $SCRIPT_VERSION"
  say "date: $(date)"
  say "phone: $MODEL"
  say "oneui: $ONEUI (raw $ONEUI_RAW)"
  say "android: $ANDROID (sdk $(getprop ro.build.version.sdk 2>/dev/null))"
  say "hexnext builds:${HN_ALL:- none}"
  say "hexnext scan report seen: ${SCAN_SEEN:-no}"
  say "hexnext apply report seen: ${APPLY_SEEN:-no}"
  say "hexnext overlays: $HN_OVERLAYS_ON on of $HN_OVERLAYS_ALL"
  say "samsung palette overlays (SemWT): $SEMWT_ON on of $SEMWT_ALL"
  say "frro files copied: $(ls "$R/frro" 2>/dev/null | grep -c .)"
  say "target apps found: $found of $count"
  say "resource tables: $(ls "$R/arsc" 2>/dev/null | grep -c .)"
  say "unzip tool: ${UNZIP:-none}"
  say "xml files: $(find "$R/xml" -type f 2>/dev/null | grep -c .) ${XML_NOTE}"
  say "system ui classes: $(grep -c . "$R/systemui-classes.txt" 2>/dev/null)"
  say "screenshots: $shot_n"
  say "notes for the tester:${NOTES:- none}"
} >"$R/00-summary.txt" 2>&1

NAME="HexNextTest-OneUI$(clean "$ONEUI")-$(clean "$MODEL")-$STAMP.tar.gz"
if ! ( cd "$W" && tar -czf "$W/$NAME" hexnext-test ) 2>/dev/null || [ ! -s "$W/$NAME" ]; then
  rule
  say " The result could not be packed (the tar tool failed)."
  say " Please take a screenshot of this window and send it instead."
  rule
  exit 1
fi

DEST=
for d in "${HEXNEXT_OUT:-}" /sdcard/Download /storage/emulated/0/Download /data/media/0/Download; do
  [ -n "$d" ] && [ -d "$d" ] || continue
  if cp "$W/$NAME" "$d/$NAME" 2>/dev/null && [ -s "$d/$NAME" ]; then
    DEST=$d/$NAME
    case "$d" in
      /data/media/*)
        chown media_rw:media_rw "$DEST" 2>/dev/null; chmod 664 "$DEST" 2>/dev/null
        am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d "file:///storage/emulated/0/Download/$NAME" >/dev/null 2>&1
        ;;
    esac
    break
  fi
done
if [ -z "$DEST" ]; then
  rule
  say " The result file could not be saved to the Downloads folder."
  say " Please take a screenshot of this window and send it instead."
  rule
  exit 1
fi
SIZE_MB=$(( ($(wc -c <"$DEST" | tr -d ' ') + 524288) / 1048576 ))
[ "$SIZE_MB" -gt 0 ] || SIZE_MB=1

say ""
rule
if [ -n "$NOTES" ]; then
  say " ALMOST DONE. One thing is missing:"
  say "$NOTES"
  say ""
  say " Cannot do that? Then send the file below anyway."
else
  say " DONE. Thank you for helping!"
fi
say ""
say " Your result is ONE file in the Downloads folder"
say " (open the My Files app, then tap Downloads):"
say ""
say "   $NAME"
say "   (about $SIZE_MB MB)"
say ""
say " Send that file to the person who asked you to run"
say " this test. Too big to attach? Upload it to Google"
say " Drive and send the link."
rule
exit 0
