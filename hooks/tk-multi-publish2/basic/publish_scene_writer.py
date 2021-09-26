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
import itertools

import sgtk
from sgtk.util.filesystem import ensure_folder_exists


import GafferUI
import GafferScene
import GafferImage
from GafferUI.FileMenu import __pathAndBookmarks


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


HookBaseClass = sgtk.get_hook_baseclass()


class GafferSceneWriterPublishPlugin(HookBaseClass):
    """
    Plugin for publishing an open gaffer ImageWriter.

    This hook relies on functionality found in the base file publisher hook in
    the publish2 app and should inherit from it in the configuration. The hook
    setting for this plugin should look something like this::

        hook: "{self}/publish_file.py:{engine}/tk-multi-publish2/basic/publish_image_writer.py"

    """

    # NOTE: The plugin icon and name are defined by the base file plugin.

    @property
    def description(self):
        """
        Verbose, multi-line description of what the plugin does. This can
        contain simple html for formatting.
        """

        loader_url = "https://support.shotgunsoftware.com/hc/en-us/articles/219033078"

        return """
        Publishes the file to Shotgun. A <b>Publish</b> entry will be
        created in Shotgun which will include a reference to the file's current
        path on disk. If a publish template is configured, a copy of the
        current ImageWriter will be copied to the publish template path which
        will be the file that is published. Other users will be able to access
        the published file via the <b><a href='%s'>Loader</a></b> so long as
        they have access to the file's location on disk.

        If the ImageWriter has not been saved, validation will fail and a button
        will be provided in the logging output to save the file.

        <h3>File versioning</h3>
        If the filename contains a version number, the process will bump the
        file to the next version after publishing.

        The <code>version</code> field of the resulting <b>Publish</b> in
        Shotgun will also reflect the version number identified in the filename.
        The basic worklfow recognizes the following version formats by default:

        <ul>
        <li><code>filename.v###.ext</code></li>
        <li><code>filename_v###.ext</code></li>
        <li><code>filename-v###.ext</code></li>
        </ul>

        After publishing, if a version number is detected in the work file, the
        work file will automatically be saved to the next incremental version
        number. For example, <code>filename.v001.ext</code> will be published
        and copied to <code>filename.v002.ext</code>

        If the next incremental version of the file already exists on disk, the
        validation step will produce a warning, and a button will be provided in
        the logging output which will allow saving the ImageWriter to the next
        available version number prior to publishing.

        <br><br><i>NOTE: any amount of version number padding is supported. for
        non-template based workflows.</i>

        <h3>Overwriting an existing publish</h3>
        In non-template workflows, a file can be published multiple times,
        however only the most recent publish will be available to other users.
        Warnings will be provided during validation if there are previous
        publishes.
        """ % (
            loader_url,
        )

    @property
    def settings(self):
        """
        Dictionary defining the settings that this plugin expects to receive
        through the settings parameter in the accept, validate, publish and
        finalize methods.

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

        # inherit the settings from the base publish plugin
        base_settings = super(GafferSceneWriterPublishPlugin, self).settings or {}

        # settings specific to this class
        gaffer_publish_settings = {
            "Publish Template": {
                "type": "template",
                "default": None,
                "description": "Template path for SceneWriter files. Should"
                "correspond to a template defined in "
                "templates.yml.",
            }
        }

        # update the base settings
        base_settings.update(gaffer_publish_settings)

        return base_settings

    @property
    def item_filters(self):
        """
        List of item types that this plugin is interested in.

        Only items matching entries in this list will be presented to the
        accept() method. Strings can contain glob patters such as *, for example
        ["gaffer.*", "file.gaffer"]
        """
        return ["gaffer.SceneCache"]

    def accept(self, settings, item):
        """
        Method called by the publisher to determine if an item is of any
        interest to this plugin. Only items matching the filters defined via the
        item_filters property will be presented to this method.

        A publish task will be generated for each item accepted here. Returns a
        dictionary with the following booleans:

            - accepted: Indicates if the plugin is interested in this value at
                all. Required.
            - enabled: If True, the plugin will be enabled in the UI, otherwise
                it will be disabled. Optional, True by default.
            - visible: If True, the plugin will be visible in the UI, otherwise
                it will be hidden. Optional, True by default.
            - checked: If True, the plugin will be checked in the UI, otherwise
                it will be unchecked. Optional, True by default.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process

        :returns: dictionary with boolean keys accepted, required and enabled
        """

        # if a publish template is configured, disable context change. This
        # is a temporary measure until the publisher handles context switching
        # natively.
        if settings.get("Publish Template").value:
            item.context_change_allowed = False

        path = _session_path()

        if not path:
            # the ImageWriter has not been saved before (no path determined).
            # provide a save button. the ImageWriter will need to be saved before
            # validation will succeed.
            self.logger.warn(
                "The Gaffer Session has not been saved.", extra=_get_save_as_action()
            )

        self.logger.info(
            "Gaffer '%s' plugin accepted the current Gaffer ImageWriter." % (self.name,)
        )
        return {"accepted": True, "checked": True}

    def validate(self, settings, item):
        """
        Validates the given item to check that it is ok to publish. Returns a
        boolean to indicate validity.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        :returns: True if item is valid, False otherwise.
        """

        publisher = self.parent
        path = _session_path()

        # ---- ensure the ImageWriter has been saved

        if not path:
            # the ImageWriter still requires saving. provide a save button.
            # validation fails.
            error_msg = "The Gaffer Session has not been saved."
            self.logger.error(error_msg, extra=_get_save_as_action())
            raise Exception(error_msg)

        # ---- check the ImageWriter against any attached work template

        # get the path in a normalized state. no trailing separator,
        # separators are appropriate for current os, no double separators,
        # etc.
        path = sgtk.util.ShotgunPath.normalize(path)

        # if the ImageWriter item has a known work template, see if the path
        # matches. if not, warn the user and provide a way to save the file to
        # a different path
        work_template = item.properties.get("work_template")
        if work_template:
            if not work_template.validate(path):
                self.logger.warning(
                    "The current ImageWriter does not match the configured work "
                    "file template.",
                    extra={
                        "action_button": {
                            "label": "Save File",
                            "tooltip": "Save the current Gaffer Session to a "
                            "different file name",
                            # will launch wf2 if configured
                            "callback": _get_save_as_action(),
                        }
                    },
                )
            else:
                self.logger.debug("Work template configured and matches session file.")
        else:
            self.logger.debug("No work template configured.")

        # ---- populate the necessary properties and call base class validation

        # populate the publish template on the item if found
        publish_template_setting = settings.get("Publish Template")
        publish_template = publisher.engine.get_template_by_name(
            publish_template_setting.value
        )
        if publish_template:
            item.properties["publish_template"] = publish_template

        # set the ImageWriter path on the item for use by the base plugin validation
        # step. NOTE: this path could change prior to the publish phase.
        item.properties["path"] = path

        # run the base class validation
        return super(GafferSceneWriterPublishPlugin, self).validate(settings, item)

    def get_publish_path(self, settings, item):
        """
        Get a publish path for the supplied settings and item.
        :param settings: This plugin instance's configured settings
        :param item: The item to determine the publish path for
        :return: A string representing the output path to supply when
            registering a publish for the supplied item
        Extracts the publish path via the configured work and publish templates
        if possible.
        """

        # publish type explicitly set or defined on the item
        publish_path = item.get_property("publish_path")
        if publish_path:
            return publish_path

        # fall back to template/path logic
        path = item.properties.path

        work_template = item.properties.get("work_template")
        writer_path = item.properties.get("writer_path")
        _, ext = os.path.splitext(writer_path)

        writer_node = item.properties.get("node")
        node_name = writer_node.getName()

        publish_template = self.get_publish_template(settings, item)

        work_fields = {}
        publish_path = None

        # We need both work and publish template to be defined for template
        # support to be enabled.
        if work_template and publish_template:
            if work_template.validate(path):
                work_fields = work_template.get_fields(path)

            work_fields["extension"] = ext[1:]
            work_fields["name"] = node_name

            missing_keys = publish_template.missing_keys(work_fields)

            if missing_keys:
                self.logger.warning(
                    "Not enough keys to apply work fields (%s) to "
                    "publish template (%s)" % (work_fields, publish_template)
                )
            else:
                # make sure we preserve the image extension
                publish_path = publish_template.apply_fields(work_fields)
                self.logger.debug(
                    "Used publish template to determine the publish path: %s"
                    % (publish_path,)
                )
        else:
            self.logger.debug("publish_template: %s" % publish_template)
            self.logger.debug("work_template: %s" % work_template)

        if not publish_path:
            publish_path = path
            self.logger.debug(
                "Could not validate a publish template. Publishing in place."
            )

        return publish_path

    def publish(self, settings, item):
        """
        Executes the publish logic for the given item and settings.

        :param settings: Dictionary of Settings. The keys are strings, matching
            the keys returned in the settings property. The values are `Setting`
            instances.
        :param item: Item to process
        """

        # get the path in a normalized state. no trailing separator, separators
        # are appropriate for current os, no double separators, etc.
        path = sgtk.util.ShotgunPath.normalize(_session_path())

        # update the item with the saved ImageWriter path
        item.properties["path"] = path

        # add dependencies for the base class to register when publishing
        item.properties[
            "publish_dependencies"
        ] = _gaffer_find_additional_image_writer_dependencies()

        # let the base class register the publish
        super(GafferSceneWriterPublishPlugin, self).publish(settings, item)


def nodes_of_type(node_type, node=None, result=None):
    if result is None:
        result = []

    if isinstance(node, node_type):
        result.append(node)

    for child in node.children():
        nodes_of_type(node_type, node=child, result=result)

    return result


def _gaffer_find_additional_image_writer_dependencies():
    """
    Find additional dependencies from the ImageWriter
    """
    # Figure out what read nodesread nodes are used by this write node and use
    # them as dependencies

    return []


def _session_path():
    """
    Return the path to the current session
    :return:
    """
    engine = sgtk.platform.current_engine()
    current_script_filename = engine.script["fileName"].getValue()
    return current_script_filename


def _save_session(path):
    """
    Save the current session to the supplied path.
    """

    # Ensure that the folder is created when saving
    folder = os.path.dirname(path)
    ensure_folder_exists(folder)

    engine = sgtk.platform.current_engine()
    script = engine.script

    script["fileName"].setValue(path)
    with GafferUI.ErrorDialogue.ErrorHandler(
        title="Error Saving File", parentWindow=engine.script_window
    ):
        script.serialiseToFile(path)


# TODO: method duplicated in all the gaffer hooks
def _get_save_as_action():
    """
    Simple helper for returning a log action dict for saving the session
    """

    engine = sgtk.platform.current_engine()

    callback = _save_as

    # if workfiles2 is configured, use that for file save
    if "tk-multi-workfiles2" in engine.apps:
        app = engine.apps["tk-multi-workfiles2"]
        if hasattr(app, "show_file_save_dlg"):
            callback = app.show_file_save_dlg

    return {
        "action_button": {
            "label": "Save As...",
            "tooltip": "Save the current session",
            "callback": callback,
        }
    }


def _save_as():
    engine = sgtk.platform.current_engine()

    path, bookmarks = __pathAndBookmarks(engine.script_window)

    dialogue = GafferUI.PathChooserDialogue(
        path, title="Save script", confirmLabel="Save", leaf=True, bookmarks=bookmarks
    )
    path = dialogue.waitForPath(parentWindow=engine.script_window)

    if not path:
        return

    path = str(path)
    if not path.endswith(".gfr"):
        path += ".gfr"

    engine.script["fileName"].setValue(path)
    with GafferUI.ErrorDialogue.ErrorHandler(
        title="Error Saving File", parentWindow=engine.script_windowWindow
    ):
        engine.script.save()
