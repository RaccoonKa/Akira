import sys

if sys.platform == "win32":
    from core.system.volume_ducker_win import VolumeDucker
else:
    from core.system.volume_ducker_linux import VolumeDucker

volume_ducker = VolumeDucker()
