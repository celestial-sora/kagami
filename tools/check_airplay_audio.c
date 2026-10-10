/* Synthetic ALAC through the owned backend's actual decoder, in memory only. */
#include <stdio.h>
#include <gst/app/gstappsink.h>
#include UXPLAY_AUDIO_SOURCE

static void quiet_log(void *context, int level, const char *message) {}

int main(int argc, char **argv) {
    gst_init(&argc, &argv);
    logger_t *test_logger = logger_init();
    logger_set_callback(test_logger, quiet_log, NULL);
    bool no_sync = false;
    audio_renderer_init(test_logger, "appsink name=decoded max-buffers=8 drop=true",
                        &no_sync, &no_sync, "");
    /* A stalled output must never let the compressed appsrc queue grow. */
    guint64 queued = 0, limit = 0;
    gint leaky = 0;
    g_object_get(renderer_type[0]->appsrc, "max-buffers", &limit, "leaky-type", &leaky, NULL);
    if (limit != 64 || leaky != 2) return 6;
    for (int n = 0; n < 1000; n++) {
        gst_app_src_push_buffer(GST_APP_SRC(renderer_type[0]->appsrc), gst_buffer_new_allocate(NULL, 64, NULL));
    }
    g_object_get(renderer_type[0]->appsrc, "current-level-buffers", &queued, NULL);
    if (queued > limit) return 7;
    GstElement *encoder = gst_parse_launch(
        "audiotestsrc num-buffers=8 samplesperbuffer=4096 volume=0.3 ! "
        "audio/x-raw,format=S16LE,rate=44100,channels=2 ! avenc_alac ! "
        "appsink name=encoded sync=false", NULL);
    GstElement *encoded = gst_bin_get_by_name(GST_BIN(encoder), "encoded");
    gst_element_set_state(encoder, GST_STATE_PLAYING);
    unsigned char ct = 2;
    unsigned short seq = 0;
    unsigned decoded_count = 0;
    GstElement *decoded = gst_bin_get_by_name(GST_BIN(renderer_type[1]->pipeline), "decoded");
    for (int i = 0; i < 8; i++) {
        GstSample *sample = gst_app_sink_try_pull_sample(GST_APP_SINK(encoded), GST_SECOND);
        if (!sample) return 2;
        /* The synthetic encoder uses 4096 samples rather than AirPlay's 352. */
        if (i == 0) {
            g_object_set(renderer_type[1]->appsrc, "caps", gst_sample_get_caps(sample), NULL);
            audio_renderer_start(&ct);
            audio_renderer_set_volume(1.0);
        }
        GstMapInfo map;
        gst_buffer_map(gst_sample_get_buffer(sample), &map, GST_MAP_READ);
        int size = map.size;
        uint64_t timestamp = gst_audio_pipeline_base_time + GST_SECOND;
        audio_renderer_render_buffer(map.data, &size, &seq, &timestamp);
        gst_buffer_unmap(gst_sample_get_buffer(sample), &map);
        gst_sample_unref(sample);
        seq++;
        sample = gst_app_sink_try_pull_sample(GST_APP_SINK(decoded), GST_SECOND);
        if (!sample) return 3;
        gst_buffer_map(gst_sample_get_buffer(sample), &map, GST_MAP_READ);
        gboolean nonzero = FALSE;
        for (gsize n = 0; n < map.size; n++) nonzero |= map.data[n] != 0;
        if (map.size == 0 || !nonzero) return 4;
        decoded_count++;
        gst_buffer_unmap(gst_sample_get_buffer(sample), &map);
        gst_sample_unref(sample);
    }
    audio_renderer_stop();
    GstState state;
    gst_element_get_state(renderer_type[1]->pipeline, &state, NULL, GST_SECOND);
    if (state != GST_STATE_NULL || renderer != NULL) return 5;
    gst_element_set_state(encoder, GST_STATE_NULL);
    gst_object_unref(encoded);
    gst_object_unref(encoder);
    gst_object_unref(decoded);
    audio_renderer_destroy();
    logger_destroy(test_logger);
    printf("Actual UxPlay audio renderer: %u non-silent ALAC buffers decoded; Stop releases audio.\n", decoded_count);
    return 0;
}
