"""Safe recognition of the Switch update prompt shown while starting software."""

from __future__ import annotations

import numpy as np


START_WITHOUT_UPDATE = "start_without_update"
UPDATE_SELECTED = "update_selected"

START_WITHOUT_CARD = "start_without_card"
CARD_PROMPT_OTHER_SELECTED = "card_prompt_other_selected"


def _scaled_rect(frame, normalized_rect):
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = normalized_rect
    return (
        max(0, min(width, int(round(width * x1)))),
        max(0, min(height, int(round(height * y1)))),
        max(0, min(width, int(round(width * x2)))),
        max(0, min(height, int(round(height * y2)))),
    )


def _border_score(mask, rect, thickness_ratio=0.025):
    x1, y1, x2, y2 = rect
    roi = mask[y1:y2, x1:x2]
    if roi.size == 0:
        return 0.0
    thickness = max(2, int(round(
        min(roi.shape[:2]) * float(thickness_ratio))))
    border = np.zeros(roi.shape, dtype=bool)
    border[:thickness, :] = True
    border[-thickness:, :] = True
    border[:, :thickness] = True
    border[:, -thickness:] = True
    return float(np.count_nonzero(roi & border)) / float(
        np.count_nonzero(border))


def detect_switch_update_prompt_selection(frame):
    """Return the safely actionable selection on the 16:9 Switch prompt.

    Detection deliberately uses the cyan selection outline and the large white
    system dialog rather than text OCR.  Unknown layouts return ``None`` so a
    caller never confirms an update based on an uncertain screen.
    """
    if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 3:
        return None
    height, width = frame.shape[:2]
    if width < 640 or height < 360:
        return None

    # Normalized from the standard Switch 16:9 system-update dialog.  The top
    # full-width option is 「このままはじめる」 and the lower-right option is
    # 「更新する」 (or 「インストールする」 for software data updates).
    prompt_rect = _scaled_rect(frame, (0.195, 0.240, 0.807, 0.762))
    start_rect = _scaled_rect(frame, (0.198, 0.548, 0.803, 0.648))
    update_rect = _scaled_rect(frame, (0.497, 0.648, 0.807, 0.762))

    blue = frame[:, :, 0].astype(np.int16)
    green = frame[:, :, 1].astype(np.int16)
    red = frame[:, :, 2].astype(np.int16)
    channel_max = np.maximum(np.maximum(blue, green), red)
    channel_min = np.minimum(np.minimum(blue, green), red)

    white_mask = (channel_min >= 200) & ((channel_max - channel_min) <= 45)
    x1, y1, x2, y2 = prompt_rect
    prompt = white_mask[y1:y2, x1:x2]
    if prompt.size == 0 or float(np.mean(prompt)) < 0.70:
        return None

    cyan_mask = (
        (blue >= 135)
        & (green >= 135)
        & (red <= 135)
        & (np.abs(blue - green) <= 60)
    )
    start_score = _border_score(cyan_mask, start_rect)
    update_score = _border_score(cyan_mask, update_rect)
    selection_threshold = 0.055

    if start_score >= selection_threshold and start_score > update_score:
        return START_WITHOUT_UPDATE
    if update_score >= selection_threshold and update_score > start_score:
        return UPDATE_SELECTED
    return None


def detect_switch_virtual_card_prompt_selection(frame):
    """Return the safely actionable selection on the 16:9 virtual game card
    prompt ("追加コンテンツをあそぶには、バーチャルゲームカードをこの本体
    にセットしてください。").

    Like detect_switch_update_prompt_selection, detection deliberately uses
    the cyan selection outline and the large white system dialog rather than
    text OCR.  This prompt's bottom row is split between 「やめる」 and
    「セットする」, so rather than calibrating a second cyan-border check
    against each half-width button (unreliable, since either one could hold
    only half of the combined row), any layout where the top 「このまま
    はじめる」 option is *not* the cyan-highlighted selection is reported as
    CARD_PROMPT_OTHER_SELECTED -- the caller only needs to know whether to
    keep pressing up, not which of the other two buttons is selected.
    Unknown layouts return ``None`` so a caller never presses A based on an
    uncertain screen.
    """
    if frame is None or not hasattr(frame, "shape") or len(frame.shape) < 3:
        return None
    height, width = frame.shape[:2]
    if width < 640 or height < 360:
        return None

    # Normalized from the standard Switch virtual-game-card prompt.  The top
    # full-width option is 「このままはじめる」 and the bottom row holds
    # 「やめる」(left) / 「セットする」(right).
    prompt_rect = _scaled_rect(frame, (0.200, 0.100, 0.800, 0.903))
    start_rect = _scaled_rect(frame, (0.196, 0.700, 0.804, 0.810))

    blue = frame[:, :, 0].astype(np.int16)
    green = frame[:, :, 1].astype(np.int16)
    red = frame[:, :, 2].astype(np.int16)
    channel_max = np.maximum(np.maximum(blue, green), red)
    channel_min = np.minimum(np.minimum(blue, green), red)

    white_mask = (channel_min >= 200) & ((channel_max - channel_min) <= 45)
    x1, y1, x2, y2 = prompt_rect
    prompt = white_mask[y1:y2, x1:x2]
    if prompt.size == 0 or float(np.mean(prompt)) < 0.70:
        return None

    cyan_mask = (
        (blue >= 135)
        & (green >= 135)
        & (red <= 135)
        & (np.abs(blue - green) <= 60)
    )
    start_score = _border_score(cyan_mask, start_rect)
    selection_threshold = 0.055

    if start_score >= selection_threshold:
        return START_WITHOUT_CARD
    return CARD_PROMPT_OTHER_SELECTED
