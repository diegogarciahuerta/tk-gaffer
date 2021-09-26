# ----------------------------------------------------------------------------
# Copyright (c) 2021, Diego Garcia Huerta.
#
# Your use of this software as distributed in this GitHub repository, is
# governed by the MIT License
#
# Your use of the Shotgun Pipeline Toolkit is governed by the applicable
# license agreement between you and Autodesk / Shotgun.
#
# The full license is in the file LICENSE, distributed with this software.
# ----------------------------------------------------------------------------


import sgtk
from sgtk import TankError

import GafferUI


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


HookBaseClass = sgtk.get_hook_baseclass()


class FrameOperation(HookBaseClass):
    """
    Hook called to perform a frame operation with the
    current scene
    """

    def get_frame_range(self, **kwargs):
        """
        get_frame_range will return a tuple of (in_frame, out_frame)
        :returns: Returns the frame range in the form (in_frame, out_frame)
        :rtype: tuple[int, int]
        """
        engine = sgtk.platform.current_engine()

        current_in = engine.script["frameRange"]["start"].getValue() if engine else 1
        current_out = engine.script["frameRange"]["end"].getValue() if engine else 100
        return (current_in, current_out)

    def set_frame_range(self, in_frame=None, out_frame=None, **kwargs):
        """
        set_frame_range will set the frame range using `in_frame` and `out_frame`
        :param int in_frame: in_frame for the current context
            (e.g. the current shot, current asset etc)
        :param int out_frame: out_frame for the current context
            (e.g. the current shot, current asset etc)
        """
        engine = sgtk.platform.current_engine()

        if engine.script:
            engine.script["frameRange"]["start"].setValue(in_frame)
            engine.script["frameRange"]["end"].setValue(out_frame)
            playback_slider = GafferUI.Playback.acquire(engine.script.context())
            playback_slider.setFrameRange(in_frame, out_frame)
