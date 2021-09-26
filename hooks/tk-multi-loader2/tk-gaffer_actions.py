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


"""
Hook that loads defines all the available actions, broken down by publish type.
"""

import os
from contextlib import contextmanager

import sgtk
from sgtk.errors import TankError

import Gaffer
import GafferScene
import GafferImage


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


HookBaseClass = sgtk.get_hook_baseclass()


class GafferActions(HookBaseClass):

    ###########################################################################
    # public interface - to be overridden by deriving classes

    def _get_icon_path(self, icon_name, icons_folders=None):
        """
        Helper to get the full path to an icon.
        By default, the hook's ``/icons`` folder will be searched.
        Additional search paths can be provided via the ``icons_folders`` arg.
        :param icon_name: The file name of the icon. ex: "alembic.png"
        :param icons_folders: A list of icons folders to find the supplied icon
            name.
        :returns: The full path to the icon of the supplied name, or a default
            icon if the name could not be found.
        """

        # ensure the publisher's icons folder is included in the search
        app_icon_folder = os.path.join(self.disk_location, "icons")

        # build the list of folders to search
        if icons_folders:
            icons_folders.append(app_icon_folder)
        else:
            icons_folders = [app_icon_folder]

        # keep track of whether we've found the icon path
        found_icon_path = None

        # iterate over all the folders to find the icon. first match wins
        for icons_folder in icons_folders:
            icon_path = os.path.join(icons_folder, icon_name)
            if os.path.exists(icon_path):
                found_icon_path = icon_path
                break

        return found_icon_path

    def generate_actions(self, sg_publish_data, actions, ui_area):
        """
        Returns a list of action instances for a particular publish. This
        method is called each time a user clicks a publish somewhere in the UI.
        The data returned from this hook will be used to populate the actions
        menu for a publish.

        The mapping between Publish types and actions are kept in a different
        place (in the configuration) so at the point when this hook is called,
        the loader app has already established *which* actions are appropriate
        for this object.

        The hook should return at least one action for each item passed in via
        the actions parameter.

        This method needs to return detailed data for those actions, in the
        form of a list of dictionaries, each with name, params, caption and
        description keys.

        Because you are operating on a particular publish, you may tailor the
        output  (caption, tooltip etc) to contain custom information suitable
        for this publish.

        The ui_area parameter is a string and indicates where the publish is to
        be shown.
        - If it will be shown in the main browsing area, "main" is passed.
        - If it will be shown in the details area, "details" is passed.
        - If it will be shown in the history area, "history" is passed.

        Please note that it is perfectly possible to create more than one
        action "instance" for an action!
        You can for example do scene introspectionvif the action passed in
        is "character_attachment" you may for examplevscan the scene, figure
        out all the nodes where this object can bevattached and return a list
        of action instances: "attach to left hand",v"attach to right hand" etc.
        In this case, when more than  one object isvreturned for an action, use
        the params key to pass additional data into the run_action hook.

        :param sg_publish_data: Shotgun data dictionary with all the standard
                                publish fields.
        :param actions: List of action strings which have been
                        defined in the app configuration.
        :param ui_area: String denoting the UI Area (see above).
        :returns List of dictionaries, each with keys name, params, caption
         and description
        """

        app = self.parent
        app.log_debug(
            "Generate actions called for UI element %s. "
            "Actions: %s. Publish Data: %s" % (ui_area, actions, sg_publish_data)
        )

        action_instances = []

        if "scene_reader" in actions:
            action_instances.append(
                {
                    "name": "scene_reader",
                    "params": None,
                    "caption": "Scene Reader",
                    "description": (
                        "Loads the published file into a new Scene Reader node."
                    ),
                }
            )

        if "image_reader" in actions:
            action_instances.append(
                {
                    "name": "image_reader",
                    "params": None,
                    "caption": "Image Reader",
                    "description": (
                        "Loads the published file into a new Image Reader node."
                    ),
                }
            )

        return action_instances

    def execute_multiple_actions(self, actions):
        """
        Executes the specified action on a list of items.

        The default implementation dispatches each item from ``actions`` to
        the ``execute_action`` method.

        The ``actions`` is a list of dictionaries holding all the actions to
        execute.
        Each entry will have the following values:

            name: Name of the action to execute
            sg_publish_data: Publish information coming from Shotgun
            params: Parameters passed down from the generate_actions hook.

        .. note::
            This is the default entry point for the hook. It reuses the
            ``execute_action`` method for backward compatibility with hooks
             written for the previous version of the loader.

        .. note::
            The hook will stop applying the actions on the selection if an
            error is raised midway through.

        :param list actions: Action dictionaries.
        """
        app = self.parent
        for single_action in actions:
            app.log_debug("Single Action: %s" % single_action)
            name = single_action["name"]
            sg_publish_data = single_action["sg_publish_data"]
            params = single_action["params"]

            self.execute_action(name, params, sg_publish_data)

    def execute_action(self, name, params, sg_publish_data):
        """
        Execute a given action. The data sent to this be method will
        represent one of the actions enumerated by the generate_actions method.

        :param name: Action name string representing one of the items returned
                     by generate_actions.
        :param params: Params data, as specified by generate_actions.
        :param sg_publish_data: Shotgun data dictionary with all the standard
                                publish fields.
        :returns: No return value expected.
        """
        app = self.parent
        app.log_debug(
            "Execute action called for action %s. "
            "Parameters: %s. Publish Data: %s" % (name, params, sg_publish_data)
        )

        # resolve path
        # toolkit uses utf-8 encoded strings internally and Gaffer API
        # expects unicode so convert the path to ensure filenames containing
        # complex characters are supported
        path = self.get_publish_path(sg_publish_data).replace(os.path.sep, "/")

        if name == "scene_reader":
            self._create_scene_reader(path, sg_publish_data)

        if name == "image_reader":
            self._create_image_reader(path, sg_publish_data)

    ###########################################################################
    # helper methods which can be subclassed in custom hooks to fine tune the
    # behaviour of things

    def _create_scene_reader(self, path, sg_publish_data):
        """
        Creates a scene reader node and loads the publish file iinto it.

        :param path: Path to file.
        :param sg_publish_data: Shotgun data dictionary with all the standard
                                publish fields.
        """
        if not os.path.exists(path):
            raise TankError("File not found on disk - '%s'" % path)

        scene_reader_extensions = GafferScene.SceneReader.supportedExtensions()

        _, ext = os.path.splitext(path)
        if ext[1:].lower() not in scene_reader_extensions:
            raise TankError(
                "Format file '%s' is not supported by Scene Reader node. Supported Formats: %s"
                % (ext, scene_reader_extensions)
            )

        reader = GafferScene.SceneReader()
        reader["fileName"].setValue(path)

        # set the icon, a nice touch
        Gaffer.Metadata.registerValue(
            reader, "icon", self._get_icon_path("sg_logo_80px.png")
        )

        engine = sgtk.platform.current_engine()
        engine.script.addChild(reader)

    def _create_image_reader(self, path, sg_publish_data):
        """
        Creates an image reader node and loads the publish file iinto it.

        :param path: Path to file.
        :param sg_publish_data: Shotgun data dictionary with all the standard
                                publish fields.
        """
        if not os.path.exists(path):
            raise TankError("File not found on disk - '%s'" % path)

        image_reader_extensions = GafferImage.ImageReader.supportedExtensions()

        _, ext = os.path.splitext(path)
        if ext[1:].lower() not in image_reader_extensions:
            raise TankError(
                "Format file '%s' is not supported by Image Reader node. Supported Formats: %s"
                % (ext, image_reader_extensions)
            )

        reader = GafferImage.ImageReader()
        reader["fileName"].setValue(path)
        reader["missingFrameMode"].setValue(
            GafferImage.ImageReader.MissingFrameMode.Hold
        )

        # set the icon, a nice touch
        Gaffer.Metadata.registerValue(
            reader, "icon", self._get_icon_path("sg_logo_80px.png")
        )

        engine = sgtk.platform.current_engine()
        engine.script.addChild(reader)
