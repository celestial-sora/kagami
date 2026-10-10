/* Exercise the actual pinned UxPlay renderer with synthetic H264, no phone. */
#include <stdio.h>
#include <gst/app/gstappsink.h>
#include UXPLAY_VIDEO_SOURCE

static void quiet_log(void *context, int level, const char *message) {}

int main(int argc, char **argv) {
    gst_init(&argc, &argv);
    logger_t *test_logger = logger_init();
    logger_set_callback(test_logger, quiet_log, NULL);
    videoflip_t flips[2] = {NONE, NONE};
    video_renderer_init(test_logger, "Kagami timestamp QA", flips, "h264parse",
        "pt=96 config-interval=1 ! appsink name=packets sync=false max-buffers=100 drop=true",
        "avdec_h264", "videoconvert", "fakesink", "", false, false, false, false, 3, NULL);
    if (video_renderer_choose_codec(false, false) != 0) return 2;
    GstElement *encoder = gst_parse_launch(
        "videotestsrc num-buffers=12 ! video/x-raw,width=160,height=90,framerate=30/1 ! "
        "x264enc tune=zerolatency key-int-max=6 ! h264parse ! "
        "video/x-h264,stream-format=byte-stream,alignment=au ! appsink name=encoded sync=false", NULL);
    GstElement *encoded = gst_bin_get_by_name(GST_BIN(encoder), "encoded");
    GstElement *packets = gst_bin_get_by_name(GST_BIN(renderer->pipeline), "packets");
    gst_element_set_state(encoder, GST_STATE_PLAYING);
    guint32 previous = 0;
    unsigned distinct = 0, valid = 0;
    for (int i = 0; i < 12; i++) {
        GstSample *sample = gst_app_sink_try_pull_sample(GST_APP_SINK(encoded), GST_SECOND);
        if (!sample) return 3;
        GstMapInfo map;
        gst_buffer_map(gst_sample_get_buffer(sample), &map, GST_MAP_READ);
        int size = map.size, nals = 1;
        uint64_t time = gst_video_pipeline_base_time + GST_SECOND + i * GST_SECOND / 30;
        if (video_renderer_render_buffer(map.data, &size, &nals, &time)) return 4;
        gst_buffer_unmap(gst_sample_get_buffer(sample), &map);
        gst_sample_unref(sample);
        /* Drain one complete access unit, including SPS/PPS RTP packets. */
        gboolean marker = FALSE;
        for (int n = 0; n < 100 && !marker; n++) {
            sample = gst_app_sink_try_pull_sample(GST_APP_SINK(packets), GST_SECOND);
            if (!sample) return 5;
            GstBuffer *buffer = gst_sample_get_buffer(sample);
            if (GST_BUFFER_PTS_IS_VALID(buffer)) valid++;
            gst_buffer_map(buffer, &map, GST_MAP_READ);
            if (map.size < 12) return 6;
            marker = (map.data[1] & 0x80) != 0;
            guint32 timestamp = GST_READ_UINT32_BE(map.data + 4);
            if (marker && (distinct == 0 || timestamp != previous)) distinct++;
            if (marker) previous = timestamp;
            gst_buffer_unmap(buffer, &map);
            gst_sample_unref(sample);
        }
        if (!marker) return 7;
    }
    gst_element_set_state(encoder, GST_STATE_NULL);
    gst_object_unref(encoded);
    gst_object_unref(encoder);
    gst_object_unref(packets);
    video_renderer_destroy();
    logger_destroy(test_logger);
    if (distinct != 12 || valid == 0) {
        fprintf(stderr, "RTP timestamps did not advance: %u distinct, %u valid PTS\n", distinct, valid);
        return 8;
    }
    printf("Actual UxPlay renderer: 12 synthetic H264 frames have advancing RTP timestamps.\n");
    return 0;
}
