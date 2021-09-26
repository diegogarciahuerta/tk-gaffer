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
A Gaffer engine for Tank.
https://www.gafferhq.org/
"""

import os
import sys
import time
import inspect
import logging
import traceback
from functools import partial

import tank
from tank.log import LogManager
from tank.platform import Engine
from tank.util import is_windows, is_linux, is_macos

import Gaffer
import GafferUI
import IECore


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


ENGINE_NAME = "tk-gaffer"
APPLICATION_NAME = "Gaffer"


# environment variable that control if to show the compatibility warning dialog
# when Gaffer software version is above the tested one.
SHOW_COMP_DLG = "SGTK_COMPATIBILITY_DIALOG_SHOWN"

# this is the absolute minimum Gaffer version for the engine to work. Actually
# the one the engine was developed originally under, so change it at your
# own risk if needed.
MIN_COMPATIBILITY_VERSION = 0.59

# this is a place to put our persistent variables between different documents
# opened
if not hasattr(Gaffer, "shotgun"):
    Gaffer.shotgun = lambda: None

# Although the engine has logging already, this logger is needed for logging
# where an engine may not be present.
logger = LogManager.get_logger(__name__)
logger.debug("Loading engine module...")


# detects if the application has be run in batch mode or not
def is_batch_mode():
    return False
    # TODO DGH


# logging functionality
def show_error(msg):
    from PySide2.QtWidgets import QMessageBox

    if not is_batch_mode():
        QMessageBox.critical(None, "Shotgun Error | %s engine" % APPLICATION_NAME, msg)
    else:
        display_error(msg)


def show_warning(msg):
    from PySide2.QtWidgets import QMessageBox

    if not is_batch_mode():
        QMessageBox.warning(None, "Shotgun Warning | %s engine" % APPLICATION_NAME, msg)
    else:
        display_warning(msg)


def show_info(msg):
    from PySide2.QtWidgets import QMessageBox

    if not is_batch_mode():
        QMessageBox.information(
            None, "Shotgun Info | %s engine" % APPLICATION_NAME, msg
        )
    else:
        display_info(msg)


# from python 2.x string module. This will be removed as soon
# as a bug in IECore.Log with Python3 (at least in Windows OS) is
# solved (it tries to use the string.join method that is deprecated):

# Join fields with optional separator
def join(words, sep=" "):
    """join(list [,sep]) -> string

    Return a string composed of the words in list, with
    intervening occurrences of sep.  The default separator is a
    single space.

    (joinfields and join are synonymous)

    """
    return sep.join(words)


if hasattr(IECore.Log, "string"):
    IECore.Log.string.join = join


def display_error(msg):
    t = time.asctime(time.localtime())
    message = "%s - Shotgun Error | %s engine | %s " % (t, APPLICATION_NAME, msg)
    IECore.Log.error(message)
    print(message)


def display_warning(msg):
    t = time.asctime(time.localtime())
    message = "%s - Shotgun Warning | %s engine | %s " % (t, APPLICATION_NAME, msg)
    IECore.Log.warning(message)


def display_info(msg):
    t = time.asctime(time.localtime())
    message = "%s - Shotgun Information | %s engine | %s " % (t, APPLICATION_NAME, msg)
    IECore.Log.info(message)


def display_debug(msg):
    if os.environ.get("TK_DEBUG") == "1":
        t = time.asctime(time.localtime())
        message = "%s - Shotgun Debug | %s engine | %s " % (t, APPLICATION_NAME, msg)
        IECore.Log.debug(message)


# methods to support the state when the engine cannot start up
# for example if a non-tank file is loaded in Gaffer we load the project
# context if exists, so we give a chance to the user to at least
# do the basics operations.
def refresh_engine():
    """
    refresh the current engine
    """

    logger.debug("Refreshing the engine")

    engine = tank.platform.current_engine()

    if not engine:
        # If we don't have an engine for some reason then we don't have
        # anything to do.
        logger.debug(
            "%s Refresh_engine | No currently initialized engine found; aborting the refresh of the engine\n"
            % APPLICATION_NAME
        )
        return

    if not engine._script:
        logger.debug("File has not been saved yet, aborting the refresh of the engine.")
        return

    active_doc_path = engine._script["fileName"].getValue()

    if not active_doc_path:
        logger.debug("File has not been saved yet, aborting the refresh of the engine.")
        return

    # make sure path is normalized
    active_doc_path = os.path.abspath(active_doc_path)

    # we are going to try to figure out the context based on the
    # active document
    current_context = tank.platform.current_engine().context

    ctx = current_context

    # this file could be in another project altogether, so create a new
    # API instance.
    try:
        # and construct the new context for this path:
        tk = tank.sgtk_from_path(active_doc_path)
        logger.debug(
            "Extracted sgtk instance: '%r' from path: '%r'", tk, active_doc_path
        )

    except tank.TankError:
        # could not detect context from path, will use the project context
        # for menus if it exists
        message = (
            "Shotgun %s Engine could not detect the context\n"
            "from the active document. Shotgun menus will be  \n"
            "stay in the current context '%s' "
            "\n" % (APPLICATION_NAME, ctx)
        )
        display_warning(message)
        return

    ctx = tk.context_from_path(active_doc_path, current_context)
    logger.debug(
        "Given the path: '%s' the following context was extracted: '%r'",
        active_doc_path,
        ctx,
    )

    # default to project context in worse case scenario
    if not ctx:
        project_name = engine.context.project.get("name")
        ctx = tk.context_from_entity_dictionary(engine.context.project)
        logger.debug(
            (
                "Could not extract a context from the current active project "
                "path, so we revert to the current project '%r' context: '%r'"
            ),
            project_name,
            ctx,
        )

    # Only change if the context is different
    if ctx != current_context:
        try:
            engine.change_context(ctx)
        except tank.TankError:
            message = (
                "Shotgun %s Engine could not change context\n"
                "to '%r'. Shotgun menu will be disabled!.\n"
                "\n" % (APPLICATION_NAME, ctx)
            )
            display_warning(message)
            engine.create_shotgun_menu(disabled=True)


class GafferEngine(Engine):
    """
    Toolkit engine for Gaffer.
    """

    def __init__(self, *args, **kwargs):
        """
        Engine Constructor
        """
        self._dock_widgets = []
        self._script = None
        self._application = None
        self._application_menu = None
        self._script_window = None
        self._menu_generator = None
        self._creating_menu = False
        Engine.__init__(self, *args, **kwargs)

    def set_script_window(self, script_window):
        self.logger.debug("setting script_window: %s", script_window)
        self._script_window = script_window

    def set_application(self, application):
        self.logger.debug("setting application: %s", application)
        self._application = application

    def set_application_menu(self, application_menu):
        self.logger.debug("setting application menu: %s", application_menu)
        self._application_menu = application_menu

    def set_active_script(self, script):
        self.logger.debug("setting script: %s", script)
        self._script = script

    @property
    def script_window(self):
        return self._script_window

    @property
    def application(self):
        return self._application

    @property
    def application_menu(self):
        return self._application_menu

    @property
    def script(self):
        return self._script

    @property
    def context_change_allowed(self):
        """
        Whether the engine allows a context change without the need for a restart.
        """
        return self._script is not None

    @property
    def host_info(self):
        """
        :returns: A dictionary with information about the application hosting this engine.

        The returned dictionary is of the following form on success:

            {
                "name": "Gaffer",
                "version": "4.2.8",
            }

        The returned dictionary is of following form on an error preventing
        the version identification.

            {
                "name": "Gaffer",
                "version: "unknown"
            }
        """

        host_info = {"name": APPLICATION_NAME, "version": "unknown"}
        try:
            host_info["version"] = Gaffer.About.versionString()
        except Exception:
            # Fallback to 'Gaffer' initialized above
            pass
        return host_info

    def check_if_document_changed(self):
        """
        Refresh the engine if the current document has changed since the last
        time we checked.
        """
        if not self._application:
            self.logger.debug("No Application loaded")
            return

        if not self._script:
            self.logger.debug("No Script loaded")
            return

        active_document_filename = self._script["fileName"].getValue()
        if not os.path.exists(active_document_filename):
            return

        if os.path.abspath(self.active_document_filename) != active_document_filename:
            self.logger.debug(
                "Active document changed from: %s to: %s"
                % (self.active_document_filename, active_document_filename)
            )
            self.active_document_filename = os.path.abspath(active_document_filename)
            refresh_engine()

    def _on_active_doc_timer(self):
        """
        Refresh the engine if the current document has changed since the last
        time we checked.
        """
        self.check_if_document_changed()

    def pre_app_init(self):
        """
        Runs after the engine is set up but before any apps have been
        initialized.
        """
        from tank.platform.qt import QtCore

        # unicode characters returned by the shotgun api need to be converted
        # to display correctly in all of the app windows
        # tell QT to interpret C strings as utf-8
        utf8 = QtCore.QTextCodec.codecForName("utf-8")
        QtCore.QTextCodec.setCodecForCStrings(utf8)
        self.logger.debug("set utf-8 codec for widget text")

        # We use a timer instead of the notifier API as the API does not
        # inform us when the user changes views, only when they are created
        # cloned, or closed.
        # Since the restart of the engine every time a view is chosen is an
        # expensive operation, we will offer this functionality as am option
        # inside the context menu.
        self.active_document_filename = "untitled"
        self.active_doc_timer = QtCore.QTimer()
        self.active_doc_timer.timeout.connect(
            partial(self.async_execute_in_main_thread, self._on_active_doc_timer)
        )

    def init_engine(self):
        """
        Initializes the Gaffer engine.
        """
        self.logger.debug("%s: Initializing...", self)

        # check that we are running a supported OS
        if not any([is_windows(), is_linux(), is_macos()]):
            raise tank.TankError(
                "The current platform is not supported!"
                " Supported platforms "
                "are Mac, Linux 64 and Windows 64."
            )

        # check that we are running an ok version of Gaffer
        application_version = (
            Gaffer.About.milestoneVersion() + Gaffer.About.majorVersion() / 100.0
        )

        if application_version < MIN_COMPATIBILITY_VERSION:
            msg = (
                "Shotgun integration is not compatible with %s versions older than %s"
                % (APPLICATION_NAME, MIN_COMPATIBILITY_VERSION)
            )
            show_error(msg)
            raise tank.TankError(msg)

        if application_version > MIN_COMPATIBILITY_VERSION + 1:
            # show a warning that this version of Gaffer isn't yet fully tested
            # with Shotgun:
            msg = (
                "The Shotgun Pipeline Toolkit has not yet been fully "
                "tested with %s %s.  "
                "You can continue to use Toolkit but you may experience "
                "bugs or instability."
                "\n\n" % (APPLICATION_NAME, application_version)
            )

            # determine if we should show the compatibility warning dialog:
            show_warning_dlg = self.has_ui and SHOW_COMP_DLG not in os.environ

            if show_warning_dlg:
                # make sure we only show it once per session
                os.environ[SHOW_COMP_DLG] = "1"

                # check against the compatibility_dialog_min_version
                # setting
                min_ver = self.get_setting("compatibility_dialog_min_version")
                if application_version < min_ver:
                    show_warning_dlg = False

            if show_warning_dlg:
                # Note, title is padded to try to ensure dialog isn't insanely
                # narrow!
                show_info(msg)

            # always log the warning to the script editor:
            self.logger.warning(msg)

            # In the case of Windows, we have the possibility of locking up if
            # we allow the PySide shim to import QtWebEngineWidgets.
            # We can stop that happening here by setting the following
            # environment variable.

            # Note that prior PyQt5 v5.12 this module existed, after that it has
            # been separated and would not cause any issues. Since it is no
            # harm if the module is not there, we leave it just in case older
            # versions of Gaffer were using previous versions of PyQt
            # https://www.riverbankcomputing.com/software/pyqtwebengine/intro
            if is_windows():
                self.logger.debug(
                    "This application on Windows can deadlock if QtWebEngineWidgets "
                    "is imported. Setting "
                    "SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT=1..."
                )
                os.environ["SHOTGUN_SKIP_QTWEBENGINEWIDGETS_IMPORT"] = "1"

        # check that we can load the GUI libraries
        self._init_pyside()

        # default menu name is Shotgun but this can be overriden
        # in the configuration to be Sgtk in case of conflicts
        self._menu_name = "Shotgun"
        if self.get_setting("use_sgtk_as_menu_name", False):
            self._menu_name = "Sgtk"

    def get_menu(self):
        """
        Returns the menu definition for Gaffer to use.
        :return: MenuDefinition
        """
        from sgtk.platform.qt import QtGui

        app = QtGui.QApplication.instance()

        # We need to cater for when the application is loading
        # and we do not have a menu ready. Also for when there
        # are multiple scripts opened, as Gaffer uses the same
        # Python process for all of them which results in the
        # same menu, which forces us to update the engine
        # context in some cases.
        self.check_if_document_changed()

        show_warning = False
        start_time = time.time()
        while self._creating_menu or not self._menu_generator:
            if (time.time() - start_time) > 1.5 and not show_warning:
                show_warning = True
                self.show_busy(
                    "Shotgun Engine", "\nRefreshing Shotgun Menu\n\nPlease wait...\n"
                )
            app.processEvents()

        self.clear_busy()

        return self._menu_generator.get_menu_definition()

    def create_shotgun_menu(self, disabled=False):
        """
        Creates the main shotgun menu in Gaffer.
        Note that this only creates the menu, not the child actions
        :return: bool
        """

        # only create the shotgun menu if not in batch mode and menu doesn't
        # already exist
        if self.has_ui:
            # create our menu handler
            tk_gaffer = self.import_module("tk_gaffer")
            if tk_gaffer.can_create_menu(self._script):
                self.logger.debug("Creating shotgun menu...")
                self._creating_menu = True
                self._menu_generator = tk_gaffer.MenuGenerator(self, self._menu_name)
                self._menu_generator.create_menu(disabled=disabled)
                self._creating_menu = False

                # monitor for document changes
                self.logger.debug("%s: Starting active doc timer...", self)
                self.active_doc_timer.start(1000)

            else:
                self.logger.debug("Waiting for menu to be created...")
                from sgtk.platform.qt import QtCore

                QtCore.QTimer.singleShot(200, self.create_shotgun_menu)
            return True

        return False

    def post_app_init(self):
        """
        Called when all apps have initialized
        """
        tank.platform.engine.set_current_engine(self)

        # create the shotgun menu
        self.create_shotgun_menu()

        # let's close the windows created by the engine before exiting the
        # application
        from sgtk.platform.qt import QtGui

        app = QtGui.QApplication.instance()
        app.aboutToQuit.connect(self.destroy_engine)
        self._initialize_dark_look_and_feel()

        # Run a series of app instance commands at startup.
        self._run_app_instance_commands()

    def post_context_change(self, old_context, new_context):
        """
        Runs after a context change. The Gaffer event watching will be stopped
        and new callbacks registered containing the new context information.

        :param old_context: The context being changed away from.
        :param new_context: The new context being changed to.
        """

        if self.get_setting("automatic_context_switch", True):
            # finally create the menu with the new context if needed
            if old_context != new_context:
                self._menu_generator = None
                self.create_shotgun_menu()

    def _run_app_instance_commands(self):
        """
        Runs the series of app instance commands listed in the
        'run_at_startup' setting of the environment configuration YAML file.
        """

        # Build a dictionary mapping app instance names to dictionaries of
        # commands they registered with the engine.
        app_instance_commands = {}
        for (cmd_name, value) in list(self.commands.items()):
            app_instance = value["properties"].get("app")
            if app_instance:
                # Add entry 'command name: command function' to the command
                # dictionary of this app instance.
                cmd_dict = app_instance_commands.setdefault(
                    app_instance.instance_name, {}
                )
                cmd_dict[cmd_name] = value["callback"]

        # Run the series of app instance commands listed in the
        # 'run_at_startup' setting.
        for app_setting_dict in self.get_setting("run_at_startup", []):
            app_instance_name = app_setting_dict["app_instance"]

            # Menu name of the command to run or '' to run all commands of the
            # given app instance.
            setting_cmd_name = app_setting_dict["name"]

            # Retrieve the command dictionary of the given app instance.
            cmd_dict = app_instance_commands.get(app_instance_name)

            if cmd_dict is None:
                self.logger.warning(
                    "%s configuration setting 'run_at_startup' requests app"
                    " '%s' that is not installed.",
                    self.name,
                    app_instance_name,
                )
            else:
                if not setting_cmd_name:
                    # Run all commands of the given app instance.
                    for (cmd_name, command_function) in list(cmd_dict.items()):
                        msg = (
                            "%s startup running app '%s' command '%s'.",
                            self.name,
                            app_instance_name,
                            cmd_name,
                        )
                        self.logger.debug(msg)

                        command_function()
                else:
                    # Run the command whose name is listed in the
                    # 'run_at_startup' setting.
                    command_function = cmd_dict.get(setting_cmd_name)
                    if command_function:
                        msg = (
                            "%s startup running app '%s' command '%s'.",
                            self.name,
                            app_instance_name,
                            setting_cmd_name,
                        )
                        self.logger.debug(msg)

                        command_function()
                    else:
                        known_commands = ", ".join("'%s'" % name for name in cmd_dict)
                        self.logger.warning(
                            "%s configuration setting 'run_at_startup' "
                            "requests app '%s' unknown command '%s'. "
                            "Known commands: %s",
                            self.name,
                            app_instance_name,
                            setting_cmd_name,
                            known_commands,
                        )

    def destroy_engine(self):
        """
        Let's close the windows created by the engine before exiting the
        application
        """
        self.logger.debug("%s: Destroying...", self)
        self.close_windows()

    def _init_pyside(self):
        """
        Checks if we can load PySide2 in this application
        """

        # import QtWidgets first or we are in trouble
        try:
            import PySide2
        except Exception as e:
            traceback.print_exc()
            self.logger.error(
                "PySide2 could not be imported! Apps using UI"
                " will not operate correctly!"
                "Error reported: %s",
                e,
            )

    def _get_dialog_parent(self):
        """
        Get the QWidget parent for all dialogs created through
        show_dialog & show_modal.
        """
        if not self._script:
            return None

        return GafferUI.ScriptWindow.acquire(self._script)._qtWidget()

    def show_panel(self, panel_id, title, bundle, widget_class, *args, **kwargs):
        """
        Docks an app widget in a Gaffer Docket, (conveniently borrowed from the
        tk-3dsmax engine)
        :param panel_id: Unique identifier for the panel, as obtained by register_panel().
        :param title: The title of the panel
        :param bundle: The app, engine or framework object that is associated with this window
        :param widget_class: The class of the UI to be constructed.
                             This must derive from QWidget.
        Additional parameters specified will be passed through to the widget_class constructor.
        :returns: the created widget_class instance
        """
        from sgtk.platform.qt import QtGui, QtCore

        dock_widget_id = "sgtk_dock_widget_" + panel_id

        main_window = self._get_dialog_parent()
        dock_widget = main_window.findChild(QtGui.QDockWidget, dock_widget_id)

        if dock_widget is None:
            # The dock widget wrapper cannot be found in the main window's
            # children list so that means it has not been created yet, so create it.
            widget_instance = widget_class(*args, **kwargs)
            widget_instance.setParent(self._get_dialog_parent())
            widget_instance.setObjectName(panel_id)

            class DockWidget(QtGui.QDockWidget):
                """
                Widget used for docking app panels that ensures the widget is closed when the
                dock is closed
                """

                closed = QtCore.pyqtSignal(QtCore.QObject)

                def closeEvent(self, event):
                    widget = self.widget()
                    if widget:
                        widget.close()
                    self.closed.emit(self)

            dock_widget = DockWidget(title, parent=main_window)
            dock_widget.setObjectName(dock_widget_id)
            dock_widget.setWidget(widget_instance)
            # Add a callback to remove the dock_widget from the list of open
            # panels and delete it
            dock_widget.closed.connect(self._remove_dock_widget)

            # Remember the dock widget, so we can delete it later.
            self._dock_widgets.append(dock_widget)
        else:
            # The dock widget wrapper already exists, so just get the
            # shotgun panel from it.
            widget_instance = dock_widget.widget()

        # apply external style sheet
        # from GafferUI._StyleSheet import _styleSheet
        # widget_instance.setStyleSheet(_styleSheet)
        # self._apply_external_stylesheet(bundle, widget_instance)

        if not main_window.restoreDockWidget(dock_widget):
            # The dock widget cannot be restored from the main window's state,
            # so dock it to the right dock area and make it float by default.
            main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dock_widget)
            dock_widget.setFloating(True)

        dock_widget.show()
        return widget_instance

    def _remove_dock_widget(self, dock_widget):
        """
        Removes a docked widget (panel) opened by the engine
        """
        self._get_dialog_parent().removeDockWidget(dock_widget)
        self._dock_widgets.remove(dock_widget)
        dock_widget.deleteLater()

    @property
    def has_ui(self):
        """
        Detect and return if Gaffer is running in batch mode
        """
        batch_mode = is_batch_mode()
        return not batch_mode

    def _emit_log_message(self, handler, record):
        """
        Called by the engine to log messages in Gaffer script editor.
        All log messages from the toolkit logging namespace will be passed to
        this method.

        :param handler: Log handler that this message was dispatched from.
                        Its default format is "[levelname basename] message".
        :type handler: :class:`~python.logging.LogHandler`
        :param record: Standard python logging record.
        :type record: :class:`~python.logging.LogRecord`
        """
        # Give a standard format to the message:
        #     Shotgun <basename>: <message>
        # where "basename" is the leaf part of the logging record name,
        # for example "tk-multi-shotgunpanel" or "qt_importer".
        if record.levelno < logging.INFO:
            formatter = logging.Formatter("Debug: Shotgun %(basename)s: %(message)s")
        else:
            formatter = logging.Formatter("Shotgun %(basename)s: %(message)s")

        msg = formatter.format(record)

        # Select Gaffer display function to use according to the logging
        # record level.
        if record.levelno >= logging.ERROR:
            fct = display_error
        elif record.levelno >= logging.WARNING:
            fct = display_warning
        elif record.levelno >= logging.INFO:
            fct = display_info
        else:
            fct = display_debug

        # Display the message in Gaffer script editor in a thread safe manner.
        self.async_execute_in_main_thread(fct, msg)

    def close_windows(self):
        """
        Closes the various windows (dialogs, panels, etc.) opened by the
        engine.
        """
        self.logger.debug("Closing all engine dialogs...")

        # Make a copy of the list of Tank dialogs that have been created by the
        # engine and are still opened since the original list will be updated
        # when each dialog is closed.
        opened_dialog_list = self.created_qt_dialogs[:]

        # Loop through the list of opened Tank dialogs.
        for dialog in opened_dialog_list:
            dialog_window_title = dialog.windowTitle()
            try:
                # Close the dialog and let its close callback remove it from
                # the original dialog list.
                dialog.close()
            except Exception as exception:
                traceback.print_exc()
                self.logger.error(
                    "Cannot close dialog %s: %s", dialog_window_title, exception
                )

        # Close all dock widgets previously added.
        for dock_widget in self._dock_widgets[:]:
            dock_widget.close()
