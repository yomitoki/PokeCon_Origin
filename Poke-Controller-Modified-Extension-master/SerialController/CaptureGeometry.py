"""Preview geometry. Capture pixels and recording timestamps never change here."""
import math


def capture_frame_size(camera):
    frame = getattr(camera, "image_bgr", None)
    if frame is not None and getattr(frame, "size", 0):
        return int(frame.shape[1]), int(frame.shape[0])
    width, height = getattr(camera, "capture_size", (1280, 720))
    return max(1, int(width)), max(1, int(height))


def fit_preview_size(source_size, available_size):
    width, height = (max(1, int(v)) for v in source_size)
    available_width, available_height = (max(1, int(v)) for v in available_size)
    scale = min(available_width / float(width), available_height / float(height))
    return max(1, int(width * scale)), max(1, int(height * scale))


def display_rect_to_capture(rect, display_size, capture_size):
    """Return clamped exclusive x1,y1,x2,y2 in original capture pixels."""
    dw, dh = display_size
    cw, ch = capture_size
    if min(dw, dh, cw, ch) <= 0:
        raise ValueError("Image dimensions must be positive")
    x1, x2 = sorted((rect[0], rect[2]))
    y1, y2 = sorted((rect[1], rect[3]))
    return (max(0, min(cw, int(math.floor(x1 * cw / dw)))),
            max(0, min(ch, int(math.floor(y1 * ch / dh)))),
            max(0, min(cw, int(math.ceil(x2 * cw / dw)))),
            max(0, min(ch, int(math.ceil(y2 * ch / dh)))))
