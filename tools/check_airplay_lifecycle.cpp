/* Exercise the actual UxPlay callbacks without a sender, renderer or network. */
#include <fcntl.h>
#include <arpa/inet.h>
extern "C" {
#include UXPLAY_NTP_HEADER
}
#define main uxplay_application_main
#include UXPLAY_APPLICATION_SOURCE
#undef main
extern "C" {
#include UXPLAY_MIRROR_HEADER
}

static bool read_disconnect(int fd, bool expected) {
    char data[8192];
    ssize_t size = read(fd, data, sizeof(data) - 1);
    bool found = false;
    if (size > 0) {
        data[size] = '\0';
        found = strstr(data, "KAGAMI_AIRPLAY_DISCONNECTED\n") != NULL;
    }
    return found == expected;
}

static void begin_video() {
    video_decode_struct data = {};
    video_process(NULL, NULL, &data);
    open_connections = 1;
    missed_feedback = 0;
    reset_httpd = reset_loop = false;
}

static void quiet_log(void *, int, const char *) {}

static bool video_eof(int events, bool partial_payload) {
    begin_video();
    logger_t *logger = logger_init();
    logger_set_callback(logger, quiet_log, NULL);
    logger_set_level(logger, LOGGER_ERR);
    raop_callbacks_t callbacks = {};
    unsigned char key[16] = {};
    timing_protocol_t timing = TP_NONE;
    raop_ntp_t *ntp = raop_ntp_init(logger, &callbacks, "127.0.0.1", 4, 0, &timing);
    if (!ntp) {
        logger_destroy(logger);
        return false;
    }
    raop_rtp_mirror_t *mirror = raop_rtp_mirror_init(logger, &callbacks, ntp, "127.0.0.1", 4, key);
    if (!mirror) {
        raop_ntp_destroy(ntp);
        logger_destroy(logger);
        return false;
    }
    uint64_t stream = 1;
    raop_rtp_mirror_init_aes(mirror, &stream);
    unsigned short port = 0;
    raop_rtp_mirror_start(mirror, &port, 0);
    int sender = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in target = {};
    target.sin_family = AF_INET;
    target.sin_port = htons(port);
    target.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    bool ok = port && sender != -1 && connect(sender, (sockaddr *) &target, sizeof(target)) == 0;
    if (ok && partial_payload) {
        unsigned char data[132] = {};
        data[0] = 16; // Declared payload is longer than the four bytes sent.
        ok = send(sender, data, sizeof(data), 0) == sizeof(data);
    }
    if (sender != -1) close(sender);
    bool received = false;
    for (int attempt = 0; ok && attempt < 100 && !received; attempt++) {
        usleep(10000);
        received = read_disconnect(events, true);
    }
    if (!ok || !received) fprintf(stderr, "Video EOF check: port=%u connected=%d event=%d partial=%d\n", port, ok, received, partial_payload);
    raop_rtp_mirror_destroy(mirror);
    raop_ntp_destroy(ntp);
    logger_destroy(logger);
    return ok && received && !kagami_mirroring.load();
}

int main() {
    // Force pipe buffering: the disconnect token must flush without stdbuf.
    setvbuf(stdout, NULL, _IOFBF, 4096);
    int events[2];
    if (pipe(events) || fcntl(events[0], F_SETFL, O_NONBLOCK) == -1) return 2;
    fflush(stdout);
    int original = dup(STDOUT_FILENO);
    if (original == -1 || dup2(events[1], STDOUT_FILENO) == -1) return 3;
    close(events[1]);
    use_video = use_audio = false;
    GMainLoop *loop = g_main_loop_new(NULL, FALSE);
    conn_init(NULL);
    conn_destroy(NULL); // Discovery probes closing are not a video disconnect.
    if (!read_disconnect(events[0], false)) return 4;

    begin_video();
    for (int seconds = 0; seconds < 600; seconds++) {
        if (seconds % 2 == 0) conn_feedback(NULL);
        if (!feedback_callback(loop) || reset_httpd || !kagami_mirroring.load()) return 5;
    }
    if (!read_disconnect(events[0], false)) return 6;
    open_connections = 2;
    conn_destroy(NULL); // Another control connection remains open.
    if (!read_disconnect(events[0], false)) return 7;
    conn_destroy(NULL);
    if (!read_disconnect(events[0], true) || kagami_mirroring.load()) return 8;

    begin_video();
    video_reset(NULL, RESET_TYPE_RTP_SHUTDOWN);
    if (!read_disconnect(events[0], true) || kagami_mirroring.load()) return 9;

    begin_video();
    conn_reset(NULL, 1);
    if (!read_disconnect(events[0], true) || kagami_mirroring.load()) return 10;

    begin_video();
    // A dead client stops /feedback, even when it stopped sending video earlier.
    for (unsigned seconds = 0; seconds <= missed_feedback_limit + 1; seconds++) {
        feedback_callback(loop);
    }
    if (!reset_httpd || !read_disconnect(events[0], true) || kagami_mirroring.load()) return 11;
    if (!video_eof(events[0], false)) return 13;
    if (!video_eof(events[0], true)) return 14;
    g_main_loop_unref(loop);
    fflush(stdout);
    if (dup2(original, STDOUT_FILENO) == -1) return 12;
    close(original);
    close(events[0]);
    puts("Actual UxPlay lifecycle: 600 idle heartbeat ticks retained; teardown, control/video TCP EOF and lost feedback disconnect through a flushed event.");
    return 0;
}
