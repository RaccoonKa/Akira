import sys

if sys.platform == "win32":
    from core.system.audio_control_win import (
        volume_up,
        volume_down,
        set_volume,
        mute_volume,
        unmute_volume,
    )
else:
    from core.system.audio_control_linux import (
        volume_up,
        volume_down,
        set_volume,
        mute_volume,
        unmute_volume,
    )
