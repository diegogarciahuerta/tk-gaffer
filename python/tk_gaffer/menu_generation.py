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
Menu handling for this engine

"""

import os
import subprocess
import sys
import unicodedata

import tank
from tank.platform.qt import QtCore, QtGui
from tank.util import is_linux, is_macos, is_windows

__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"

import IECore
import GafferUI


def get_menubar(script):
    """
    Retrieves the Menu bar of the QApplication
    """
    win = GafferUI.ScriptWindow.acquire(script)
    return win.menuBar()._qtWidget()


def can_create_menu(script):
    """
    This is used to indicate if the menu can be created in this DCC app.
    Only when there is a menu bar available we can create the menu.
    """
    return script and get_menubar(script) is not None


# borrowed from tk-maya, needed to remove the args from the QAction callbacks
class Callback(object):
    def __init__(self, callback):
        self.callback = callback

    def __call__(self, *_):
        """
        Execute the callback deferred to avoid potential problems with the
        command resulting in the menu being deleted, e.g. if the context changes
        resulting in an engine restart! - this was causing a segmentation fault
        crash on Linux.
        :param _: Accepts any args so that a callback might throw at it.
        For example a menu callback will pass the menu state. We accept these
        and ignore them.
        """
        # note that we use a single shot timer instead of cmds.evalDeferred as
        # we were experiencing odd behaviour when the deferred command presented
        # a modal dialog that then performed a file operation that resulted in a
        # QMessageBox being shown - the deferred command would then run a second
        # time, presumably from the event loop of the modal dialog from the
        # first command!
        #
        # As the primary purpose of this method is to detach the executing code
        # from the menu invocation, using a singleShot timer achieves this
        # without the odd behaviour exhibited by evalDeferred.

        # This logic is implemented in the plugin_logic.py Callback class.

        QtCore.QTimer.singleShot(0, self._execute_within_exception_trap)

    def _execute_within_exception_trap(self):
        """
        Execute the callback and log any exception that gets raised which may otherwise have been
        swallowed by the deferred execution of the callback.
        """
        try:
            self.callback()
        except Exception:
            current_engine = tank.platform.current_engine()
            current_engine.logger.exception("An exception was raised from Toolkit")


class MenuGenerator(object):
    """
    Menu generation functionality for this engine
    """

    def __init__(self, engine, menu_name):
        self._engine = engine
        self._menu_name = menu_name
        self._menu_def = None
        self._divider_id = 1
        self._menu_item_id = 1

    def create_menu(self, disabled=False):
        """
        Render the entire Shotgun menu.
        In order to have commands enable/disable themselves based on the
        enable_callback, re-create the menu items every time.
        """
        self._menu_def = IECore.MenuDefinition()

        if not disabled:
            self._engine.application_menu.setEnabled(False)
            QtGui.QApplication.processEvents()

            # now add the context item on top of the main menu
            self._context_menu = self._add_context_menu(parent_menu="")

            # add menu divider
            self._add_divider(parent_menu="")

            # now enumerate all items and create menu objects for them
            menu_items = []
            for (cmd_name, cmd_details) in self._engine.commands.items():
                self._engine.log_debug(
                    "engine command: %s : %s" % (cmd_name, cmd_details)
                )
                menu_items.append(
                    AppCommand(cmd_name, self, cmd_details, self._engine.logger)
                )

            # sort list of commands in name order
            menu_items.sort(key=lambda x: x.name)

            # now add favourites
            menu_favourites = self._engine.get_setting("menu_favourites")
            for fav in menu_favourites:
                app_instance_name = fav["app_instance"]
                menu_name = fav["name"]

                # scan through all menu items
                for cmd in menu_items:
                    self._engine.log_debug("cmd: %s" % cmd.name)
                    if (
                        cmd.get_app_instance_name() == app_instance_name
                        and cmd.name == menu_name
                    ):
                        # found our match!
                        cmd.add_command_to_menu(menu="")
                        # mark as a favourite item
                        cmd.favourite = True

            # add menu divider
            if len(menu_favourites) > 0:
                self._add_divider(parent_menu="")

            # now go through all of the menu items.
            # separate them out into various sections
            commands_by_app = {}

            for cmd in menu_items:
                if cmd.get_type() == "context_menu":
                    # context menu!
                    cmd.add_command_to_menu(self._context_menu)

                else:
                    # normal menu
                    app_name = cmd.get_app_name()
                    if app_name is None:
                        # un-parented app
                        app_name = "Other Items"
                    if app_name not in commands_by_app:
                        commands_by_app[app_name] = []
                    commands_by_app[app_name].append(cmd)

            self._engine.log_debug("about to add app menu")

            # now add all apps to main menu
            self._add_app_menu(commands_by_app)

            self._engine.application_menu.setEnabled(True)
        else:
            self._menu_def.append(
                "/menu_disabled", {"command": None, "label": "Sgtk is disabled."}
            )

    def get_menu_definition(self):
        return self._menu_def

    def _add_divider(self, parent_menu):
        self._divider_id += 1
        self._menu_def.append(
            parent_menu + "/divider%s" % self._divider_id, {"divider": True}
        )

    def _add_sub_menu(self, menu_name, parent_menu):
        return parent_menu + "/" + menu_name

    def _add_menu_item(self, name, parent_menu, callback, properties=None):
        self._menu_item_id += 1
        menu_description = {
            "command": Callback(callback) if callback else None,
            "label": name,
            "searchText": name,
        }

        if properties:
            if "tooltip" in properties:
                menu_description["description"] = properties["tooltip"]
            if "short_cut" in properties:
                menu_description["shortCut"] = properties["short_cut"]
            if "enable_callback" in properties:
                menu_description["active"] = properties["enable_callback"]()
            if "checkable" in properties:
                menu_description["checkBox"] = properties.get("checkable")
            elif "checkable_callback" in properties:
                menu_description["checkBox"] = properties.get("checkable_callback")()

        self._menu_def.append(
            parent_menu + "/%s%d" % (name, self._menu_item_id), menu_description
        )

    def _add_context_menu(self, parent_menu):
        """
        Adds a context menu which displays the current context
        """

        ctx = self._engine.context
        ctx_name = str(ctx)

        # create the menu object
        # the label expects a unicode object so we cast it to support when the
        # context may contain info with non-ascii characters

        ctx_menu = self._add_sub_menu(ctx_name, parent_menu)

        self._add_menu_item("Jump to Shotgun", ctx_menu, self._jump_to_sg)

        # Add the menu item only when there are some file system locations.
        if ctx.filesystem_locations:
            self._add_menu_item(
                "Jump to File System",
                ctx_menu,
                self._jump_to_fs,
                properties={"tooltip": "my tooliotoop"},
            )

        # divider (apps may register entries below this divider)
        self._add_divider(ctx_menu)

        return ctx_menu

    def _jump_to_sg(self):
        """
        Jump to shotgun, launch web browser
        """
        url = self._engine.context.shotgun_url
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def _jump_to_fs(self):
        """
        Jump from context to FS
        """
        # launch one window for each location on disk
        paths = self._engine.context.filesystem_locations
        for disk_location in paths:

            # get the setting
            system = sys.platform

            # run the app
            if is_linux():
                args = ["xdg-open", disk_location]
            elif is_macos():
                args = ['open "%s"', disk_location]
            elif is_windows():
                args = ["cmd.exe", "/C", "start", '"Folder %s"' % disk_location]
            else:
                raise Exception("Platform '%s' is not supported." % system)

            exit_code = subprocess.check_output(args, shell=False)
            if exit_code != 0:
                self._engine.logger.error("Failed to launch '%s'!", args)

    def _add_app_menu(self, commands_by_app):
        """
        Add all apps to the main menu, process them one by one.
        """
        for app_name in sorted(commands_by_app.keys()):
            if len(commands_by_app[app_name]) > 1:
                # more than one menu entry fort his app
                # make a sub menu and put all items in the sub menu
                app_menu = self._add_sub_menu(app_name, "")

                # get the list of menu cmds for this app
                cmds = commands_by_app[app_name]
                # make sure it is in alphabetical order
                cmds.sort(key=lambda x: x.name)

                for cmd in cmds:
                    cmd.add_command_to_menu(app_menu)
            else:
                # this app only has a single entry.
                # display that on the menu
                cmd_obj = commands_by_app[app_name][0]
                if not cmd_obj.favourite:
                    # skip favourites since they are already on the menu
                    cmd_obj.add_command_to_menu(menu="")
        self._add_divider(parent_menu="")


class AppCommand(object):
    """
    Wraps around a single command that you get from engine.commands
    """

    def __init__(self, name, parent, command_dict, logger):
        self.name = name
        self.parent = parent
        self.properties = command_dict["properties"] or {}
        self.callback = command_dict["callback"]
        self.favourite = False
        self.logger = logger

    def get_app_name(self):
        """
        Returns the name of the app that this command belongs to
        """
        if "app" in self.properties:
            return self.properties["app"].display_name
        return None

    def get_app_instance_name(self):
        """
        Returns the name of the app instance, as defined in the environment.
        Returns None if not found.
        """
        if "app" not in self.properties:
            return None

        app_instance = self.properties["app"]
        engine = app_instance.engine

        for (app_instance_name, app_instance_obj) in engine.apps.items():
            if app_instance_obj == app_instance:
                # found our app!
                return app_instance_name

        return None

    def get_documentation_url_str(self):
        """
        Returns the documentation as a str
        """
        if "app" in self.properties:
            app = self.properties["app"]
            doc_url = app.documentation_url
            # deal with nuke's inability to handle unicode. #fail
            if doc_url.__class__ == unicode:
                doc_url = unicodedata.normalize("NFKD", doc_url).encode(
                    "ascii", "ignore"
                )
            return doc_url

        return None

    def get_type(self):
        """
        returns the command type. Returns node, custom_pane or default
        """
        return self.properties.get("type", "default")

    def add_command_to_menu(self, menu):
        """
        Adds an app command to the menu
        """

        self.parent._add_menu_item(self.name, menu, self.callback, self.properties)

        # # create menu sub-tree if need to:
        # # Support menu items seperated by '/'
        # parent_menu = menu

        # parts = self.name.split("/")
        # for item_label in parts[:-1]:
        #     # see if there is already a sub-menu item
        #     sub_menu = self._find_sub_menu_item(parent_menu, item_label)
        #     if sub_menu:
        #         # already have sub menu
        #         parent_menu = sub_menu
        #     else:
        #         parent_menu = self.parent._add_sub_menu(item_label, parent_menu)

        # # self._execute_deferred)
        # self.parent._add_menu_item(parts[-1], parent_menu, self.callback, self.properties)
