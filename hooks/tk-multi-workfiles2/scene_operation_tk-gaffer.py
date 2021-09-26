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

    def execute(
        self,
        operation,
        file_path,
        context,
        parent_action,
        file_version,
        read_only,
        **kwargs
    ):
        """
        Main hook entry point

        :param operation:       String
                                Scene operation to perform

        :param file_path:       String
                                File path to use if the operation
                                requires it (e.g. open)

        :param context:         Context
                                The context the file operation is being
                                performed in.

        :param parent_action:   This is the action that this scene operation is
                                being executed for.  This can be one of:
                                - open_file
                                - new_file
                                - save_file_as
                                - version_up

        :param file_version:    The version/revision of the file to be opened.  If this is 'None'
                                then the latest version should be opened.

        :param read_only:       Specifies if the file should be opened read-only or not

        :returns:               Depends on operation:
                                'current_path' - Return the current scene
                                                 file path as a String
                                'reset'        - True if scene was reset to an empty
                                                 state, otherwise False
                                all others     - None
        """
        app = self.parent
        engine = sgtk.platform.current_engine()

        app.log_debug("-" * 50)
        app.log_debug("operation: %s" % operation)
        app.log_debug("file_path: %s" % file_path)
        app.log_debug("context: %s" % context)
        app.log_debug("parent_action: %s" % parent_action)
        app.log_debug("file_version: %s" % file_version)
        app.log_debug("read_only: %s" % read_only)

        if operation == "current_path":
            current_script_filename = engine.script["fileName"].getValue()
            return current_script_filename

        elif operation == "open":
            open_script(engine.script, file_path)

        elif operation == "save":
            script = engine.script
            if script["fileName"].getValue():
                with GafferUI.ErrorDialogue.ErrorHandler(
                    title="Error Saving File", parentWindow=engine.script_window
                ):
                    script.save()

        elif operation == "save_as":
            script = engine.script

            script["fileName"].setValue(file_path)
            with GafferUI.ErrorDialogue.ErrorHandler(
                title="Error Saving File", parentWindow=engine.script_window
            ):
                script.save()

            addRecentFile(engine.application, file_path)

        elif operation == "reset":
            return True
