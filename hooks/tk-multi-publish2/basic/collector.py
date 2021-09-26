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

import glob
import os

import sgtk

import GafferScene
import GafferImage

__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


HookBaseClass = sgtk.get_hook_baseclass()


class GafferSessionCollector(HookBaseClass):
    """
    Collector that operates on the gaffer session. Should inherit from the basic
    collector hook.
    """

    @property
    def settings(self):
        """
        Dictionary defining the settings that this collector expects to receive
        through the settings parameter in the process_current_session and
        process_file methods.

        A dictionary on the following form::

            {
                "Settings Name": {
                    "type": "settings_type",
                    "default": "default_value",
                    "description": "One line description of the setting"
            }

        The type string should be one of the data types that toolkit accepts as
        part of its environment configuration.
        """

        # grab any base class settings
        collector_settings = super(GafferSessionCollector, self).settings or {}

        # settings specific to this collector
        gaffer_session_settings = {
            "Work Template": {
                "type": "template",
                "default": None,
                "description": "Template path for artist work files. Should "
                "correspond to a template defined in "
                "templates.yml. If configured, is made available"
                "to publish plugins via the collected item's "
                "properties. ",
            }
        }

        # update the base settings with these settings
        collector_settings.update(gaffer_session_settings)

        return collector_settings

    def process_current_session(self, settings, parent_item):
        """
        Analyzes the current session open in Gaffer and parents a subtree of
        items under the parent_item passed in.

        :param dict settings: Configured settings for this collector
        :param parent_item: Root item instance

        """

        # create an item representing the current gaffer session
        session_item = self.collect_current_gaffer_session(settings, parent_item)
        self.collect_gaffer_write_nodes(settings, session_item)

    def collect_current_gaffer_session(self, settings, parent_item):
        """
        Creates an item that represents the current gaffer session.

        :param parent_item: Parent Item instance

        :returns: Item of type gaffer.session
        """

        publisher = self.parent

        # get the path to the current file
        path = _session_path()

        # determine the display name for the item
        if path:
            file_info = publisher.util.get_file_path_components(path)
            display_name = file_info["filename"]
        else:
            display_name = "Current Gaffer Session"

        # create the session item for the publish hierarchy
        session_item = parent_item.create_item(
            "gaffer.session", "Gaffer Session", display_name
        )

        # get the icon path to display for this item
        icon_path = os.path.join(self.disk_location, os.pardir, "icons", "gaffer.png")
        session_item.set_icon_from_path(icon_path)

        # if a work template is defined, add it to the item properties so
        # that it can be used by attached publish plugins
        work_template_setting = settings.get("Work Template")
        if work_template_setting:

            work_template = publisher.engine.get_template_by_name(
                work_template_setting.value
            )

            # store the template on the item for use by publish plugins. we
            # can't evaluate the fields here because there's no guarantee the
            # current session path won't change once the item has been created.
            # the attached publish plugins will need to resolve the fields at
            # execution time.
            session_item.properties["work_template"] = work_template
            session_item.properties["publish_type"] = "Gaffer File"
            self.logger.debug("Work template defined for Gaffer collection.")

        self.logger.info("Collected current Gaffer scene")

        return session_item

    def collect_gaffer_write_nodes(self, settings, parent_item):
        publisher = self.parent
        engine = sgtk.platform.current_engine()

        scene_writer_nodes = nodes_of_type(GafferScene.SceneWriter, node=engine.script)

        for node in scene_writer_nodes:
            writer_path = node["fileName"].getValue()
            writer_path = writer_path.replace("/", os.path.sep)

            if not writer_path:
                continue

            display_name = "%s (node)" % node.getName()

            # create the session item for the publish hierarchy
            writer_item = parent_item.create_item(
                "gaffer.SceneCache", "SceneCache", display_name
            )

            # get the icon path to display for this item
            icon_path = os.path.join(
                self.disk_location, os.pardir, "icons", "geometry.png"
            )
            writer_item.set_icon_from_path(icon_path)

            # if a work template is defined, add it to the item properties so
            # that it can be used by attached publish plugins
            work_template_setting = settings.get("Work Template")
            if work_template_setting:

                work_template = publisher.engine.get_template_by_name(
                    work_template_setting.value
                )

                # store the template on the item for use by publish plugins. we
                # can't evaluate the fields here because there's no guarantee the
                # current session path won't change once the item has been created.
                # the attached publish plugins will need to resolve the fields at
                # execution time.
                writer_item.properties["work_template"] = work_template
                writer_item.properties["publish_type"] = "SceneCache"
                writer_item.properties["node"] = node
                writer_item.properties["writer_path"] = writer_path

        image_writer_nodes = nodes_of_type(GafferImage.ImageWriter, node=engine.script)

        for node in image_writer_nodes:
            writer_path = node["fileName"].getValue()
            writer_path = writer_path.replace("/", os.path.sep)

            if not writer_path:
                continue

            display_name = "%s (node)" % node.getName()

            # create the session item for the publish hierarchy
            writer_item = parent_item.create_item(
                "gaffer.ImageWriter", "ImageWriter", display_name
            )

            # get the icon path to display for this item
            icon_path = os.path.join(
                self.disk_location, os.pardir, "icons", "texture.png"
            )
            writer_item.set_icon_from_path(icon_path)

            # if a work template is defined, add it to the item properties so
            # that it can be used by attached publish plugins
            work_template_setting = settings.get("Work Template")
            if work_template_setting:

                work_template = publisher.engine.get_template_by_name(
                    work_template_setting.value
                )

                # store the template on the item for use by publish plugins. we
                # can't evaluate the fields here because there's no guarantee the
                # current session path won't change once the item has been created.
                # the attached publish plugins will need to resolve the fields at
                # execution time.
                writer_item.properties["work_template"] = work_template
                writer_item.properties["publish_type"] = "Image"
                writer_item.properties["node"] = node
                writer_item.properties["writer_path"] = writer_path


def nodes_of_type(node_type, node=None, result=None):
    if result is None:
        result = []

    if isinstance(node, node_type):
        result.append(node)

    for child in node.children():
        nodes_of_type(node_type, node=child, result=result)

    return result


def _session_path():
    """
    Return the path to the current session
    :return:
    """
    engine = sgtk.platform.current_engine()
    current_script_filename = engine.script["fileName"].getValue()
    return current_script_filename
