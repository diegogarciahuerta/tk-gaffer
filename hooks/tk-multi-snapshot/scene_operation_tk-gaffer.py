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
import functools

import sgtk

import Gaffer
import GafferUI
from GafferUI.FileMenu import __open as open_script
from GafferUI.FileMenu import addRecentFile


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


HookClass = sgtk.get_hook_baseclass()


class SceneOperation(HookClass):
    """
    Hook called to perform an operation with the
    current scene
    """

    def execute(self, operation, file_path, **kwargs):
        """
        Main hook entry point

        :operation: String
                    Scene operation to perform

        :file_path: String
                    File path to use if the operation
                    requires it (e.g. open)

        :returns:   Depends on operation:
                    'current_path' - Return the current scene
                                     file path as a String
                    all others     - None
        """
        engine = sgtk.platform.current_engine()

        if operation == "current_path":
            current_script_filename = engine.script["fileName"].getValue()
            return current_script_filename

        elif operation == "open":
            # this is a trick to make gaffer reuse the same script window
            # as we are really loading the same script but a previous
            # snapshot in time
            engine.script["fileName"].setValue("")
            engine.script["unsavedChanges"].setValue(False)

            open_script(engine.script, file_path)

        elif operation == "save":
            script = engine.script
            if script["fileName"].getValue():
                with GafferUI.ErrorDialogue.ErrorHandler(
                    title="Error Saving File", parentWindow=engine.script_window
                ):
                    script.save()
