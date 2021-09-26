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


import os
import tempfile
import uuid

import sgtk

import GafferUI

HookClass = sgtk.get_hook_baseclass()


class ThumbnailHook(HookClass):
    """
    Hook that can be used to provide a pre-defined thumbnail for the app
    """

    def execute(self, **kwargs):
        """
        Main hook entry point
        :returns:       String
                        Hook should return a file path pointing to the location
                        of a thumbnail file on disk that will be used.
                        If the hook returns None then the screenshot
                        functionality will be enabled in the UI.
        """
        # get the engine name from the parent object (app/engine/etc.)
        return self._extract_engine_thumbnail()

    def _extract_engine_thumbnail(self):
        """
        Render a thumbnail for the current canvas in Natron

        :returns:   The path to the thumbnail on disk
        """
        engine = self.parent.engine
        if engine and engine.script_window:
            temp_dir = tempfile.gettempdir()
            temp_filename = "sgtk_thumb_%s.jpg" % uuid.uuid4().hex
            jpg_thumb_path = os.path.join(temp_dir, temp_filename)
            GafferUI.WidgetAlgo.grab(engine.script_window, jpg_thumb_path)

            return jpg_thumb_path

        return None
