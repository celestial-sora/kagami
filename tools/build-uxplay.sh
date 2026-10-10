#!/usr/bin/env bash
# Build the inspected UxPlay backend as the caller, stage without root.
set -euo pipefail
source_dir=${1:?Source checkout directory required}
staging_dir=${2:?Empty staging directory required}
uxplay_sha=4764e4619e8924f43601d778277fc9f0bf280597
[[ $source_dir == /* && $staging_dir == /* && ! -e $source_dir && ! -e $staging_dir ]] || {
    printf 'Use new absolute source and staging paths.\n' >&2; exit 2;
}
printf 'Kagami · Build UxPlay: downloading pinned source\n'
git init -q "$source_dir"
git -C "$source_dir" remote add origin https://github.com/FDH2/UxPlay.git
git -C "$source_dir" fetch --depth=1 origin "$uxplay_sha" < /dev/null
git -C "$source_dir" checkout -q --detach FETCH_HEAD
[[ $(git -C "$source_dir" rev-parse HEAD) == "$uxplay_sha" ]] || exit 2
# v1.73.2 uses printf here without declaring it; GCC 14+ rejects this.
# Keep the pinned source and compiler diagnostics, adding the missing header.
python3 - "$source_dir/renderers/video_renderer.c" "$source_dir/uxplay.cpp" "$source_dir/lib/raop_rtp_mirror.c" "$source_dir/renderers/audio_renderer.c" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
source = path.read_text()
fixes = (
    ('#include "video_renderer.h"\n', '#include <stdio.h>\n#include "video_renderer.h"\n', 1),
    ('static bool sync = false;\n', 'static bool sync = false;\nstatic bool timestamp_rtp = false;\n', 1),
    ('    bool rtp = (bool) strlen(rtp_pipeline);\n',
     '    bool rtp = (bool) strlen(rtp_pipeline);\n    timestamp_rtp = rtp;\n', 1),
    ('if (sync) {', 'if (sync || timestamp_rtp) {', 2),
)
# RTP forwarding bypasses the videosink sync setting. Preserve presentation
# timestamps there too, or rtph264pay emits a constant RTP timestamp and the
# receiver's videorate discards every decoded frame with CLOCK_TIME_NONE.
for anchor, replacement, count in fixes:
    if source.count(anchor) != count:
        raise SystemExit("Pinned UxPlay context changed; review the compatibility fixes.")
    source = source.replace(anchor, replacement)
path.write_text(source)
# A still screen is not a lost connection. Report protocol teardown and the
# existing client-feedback watchdog through fixed, immediately flushed tokens.
# Track actual mirrored video so discovery probes closing do not end a session.
path = Path(sys.argv[2])
source = path.read_text()
fixes = (
    ('#include <stddef.h>\n', '#include <stddef.h>\n#include <atomic>\n', 1),
    ('static gboolean feedback_callback(gpointer loop) {\n',
     'static std::atomic<bool> kagami_mirroring(false);\n'
     'extern "C" void kagami_disconnected() {\n'
     '    if (kagami_mirroring.exchange(false)) {\n'
     '        fputs("\\nKAGAMI_AIRPLAY_DISCONNECTED\\n", stdout);\n'
     '        fflush(stdout);\n'
     '    }\n'
     '}\n\n'
     'static gboolean feedback_callback(gpointer loop) {\n', 1),
    ('        if (missed_feedback_limit && missed_feedback > missed_feedback_limit) {\n',
     '        if (missed_feedback_limit && missed_feedback > missed_feedback_limit) {\n'
     '            kagami_disconnected();\n', 1),
    ('    case RESET_TYPE_RTP_SHUTDOWN:\n',
     '    case RESET_TYPE_RTP_SHUTDOWN:\n        kagami_disconnected();\n', 1),
    ('    if (open_connections == 0) {\n',
     '    if (open_connections == 0) {\n        kagami_disconnected();\n', 1),
    ('extern "C" void conn_reset (void *cls, int reason) {\n',
     'extern "C" void conn_reset (void *cls, int reason) {\n    kagami_disconnected();\n', 1),
    ('extern "C" void video_process (void *cls, raop_ntp_t *ntp, video_decode_struct *data) {\n',
     'extern "C" void video_process (void *cls, raop_ntp_t *ntp, video_decode_struct *data) {\n'
     '    kagami_mirroring.store(true);\n', 1),
    ('    printf("UxPlay %s: An open-source AirPlay mirroring server.\\n", VERSION);\n',
     '    printf("UxPlay %s: An open-source AirPlay mirroring server.\\n", VERSION);\n'
     '    puts("KAGAMI_AIRPLAY_EVENTS_V1 KAGAMI_AIRPLAY_AUDIO_V1");\n', 1),
)
for anchor, replacement, count in fixes:
    if source.count(anchor) != count:
        raise SystemExit("Pinned UxPlay context changed; review the lifecycle fixes.")
    source = source.replace(anchor, replacement)
path.write_text(source)
# A video TCP EOF can occur while a control connection still sends feedback.
# Report that EOF directly without changing upstream's reset/reconnect policy.
path = Path(sys.argv[3])
source = path.read_text()
fixes = (
    ('#include "raop.h"\n', '#include "raop.h"\nextern void kagami_disconnected(void);\n', 1),
    ('            if (payload == NULL && ret == 0) {\n',
     '            if (payload == NULL && ret == 0) {\n                kagami_disconnected();\n', 1),
    ('            if (ret == 0) {\n',
     '            if (ret == 0) {\n                kagami_disconnected();\n', 1),
)
for anchor, replacement, count in fixes:
    if source.count(anchor) != count:
        raise SystemExit("Pinned UxPlay context changed; review the video EOF fixes.")
    source = source.replace(anchor, replacement)
path.write_text(source)
# Audio is now played locally. Bound the compressed input even if the desktop
# output stalls; appsrc's default nonblocking queue otherwise grows indefinitely.
path = Path(sys.argv[4])
source = path.read_text()
anchor = '"stream-type", 0, "is-live", TRUE, "format", GST_FORMAT_TIME, NULL);'
replacement = ('"stream-type", 0, "is-live", TRUE, "format", GST_FORMAT_TIME, '
               '"max-buffers", (guint64) 64, "max-bytes", (guint64) 0, '
               '"max-time", (guint64) (2 * GST_SECOND), "leaky-type", 2, NULL);')
if source.count(anchor) != 1:
    raise SystemExit("Pinned UxPlay context changed; review the bounded audio input fix.")
path.write_text(source.replace(anchor, replacement))
PY
printf 'Kagami · Build UxPlay: configuring\n'
cmake -S "$source_dir" -B "$source_dir/build" -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/local -DNO_MARCH_NATIVE=ON -DNO_X11_DEPS=ON < /dev/null
printf 'Kagami · Build UxPlay: compiling\n'
cmake --build "$source_dir/build" --parallel 2 < /dev/null
printf 'Kagami · Build UxPlay: staging files\n'
DESTDIR="$staging_dir" cmake --install "$source_dir/build" < /dev/null
install -D -m 644 "$source_dir/LICENSE" "$staging_dir/usr/local/share/doc/kagami-uxplay/LICENSE"
install -D -m 644 "$source_dir/lib/llhttp/LICENSE-MIT" "$staging_dir/usr/local/share/doc/kagami-uxplay/LICENSE-llhttp"
printf '%s\n' "$uxplay_sha" > "$staging_dir/usr/local/share/doc/kagami-uxplay/VERSION"
