"""Versioned signaling messages, independent of GStreamer."""

PROTOCOL_VERSION = 1


def validate_signal(message):
    if not isinstance(message, dict) or type(message.get("v")) is not int or message["v"] != PROTOCOL_VERSION:
        raise ValueError("Unsupported signaling protocol. Reload the phone client.")
    kind = message.get("type")
    if kind == "offer":
        sdp = message.get("sdp")
        if not isinstance(sdp, str) or not sdp.startswith("v=0") or len(sdp) > 65536:
            raise ValueError("Invalid SDP offer.")
        media = [line for line in sdp.splitlines() if line.startswith("m=")]
        if len(media) != 1 or not media[0].startswith("m=video "):
            raise ValueError("The Phase 0 receiver accepts one video track only.")
    elif kind == "ice":
        candidate = message.get("candidate")
        if candidate is None:
            return message
        if not isinstance(candidate, dict):
            raise ValueError("Invalid ICE candidate.")
        value, index = candidate.get("candidate"), candidate.get("sdpMLineIndex")
        if not isinstance(value, str) or not value.startswith("candidate:") or len(value) > 2048 or "\n" in value or "\r" in value:
            raise ValueError("Invalid ICE candidate string.")
        if type(index) is not int or not 0 <= index <= 16:
            raise ValueError("Invalid ICE media index.")
    else:
        raise ValueError("Unexpected signaling message.")
    return message
