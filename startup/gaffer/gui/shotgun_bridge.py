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
This file is the one loader by Gaffer first and responsible to create
just the top level Shotgun Menu. It waits until the menu bar of 
the application is available to bootstrap the engine.
"""

import os
import sys
import functools

import Gaffer
import GafferUI
import IECore

__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"

ENGINE_NAME = "tk-gaffer"

boostrap_engine_script = os.environ.get("SGTK_GAFFER_ENGINE_STARTUP")

SGTK_MODULE_PATH = os.environ.get("SGTK_MODULE_PATH")
if SGTK_MODULE_PATH and SGTK_MODULE_PATH not in sys.path:
    sys.path.insert(0, SGTK_MODULE_PATH)


def find_top_level_menubar():
    import PySide2

    app = PySide2.QtWidgets.QApplication.instance()

    for widget in app.topLevelWidgets():
        menu_bars = widget.findChildren(PySide2.QtWidgets.QMenuBar)
        if menu_bars:
            return menu_bars[-1]

    return None


def shotgunMenuCallable(menu):
    scriptWindow = menu.ancestor(GafferUI.ScriptWindow)
    application = scriptWindow.scriptNode().ancestor(Gaffer.ApplicationRoot)
    script = scriptWindow.scriptNode()

    import sgtk

    engine = sgtk.platform.current_engine()
    engine.set_script_window(scriptWindow)
    engine.set_active_script(script)
    engine.set_application(application)
    engine.set_application_menu(menu)

    menuDefinition = engine.get_menu()

    return menuDefinition


def check_ui_finished_loading(*args, **kwargs):
    """
    Checks if the UI has finished loading by checking if there is a menubar
    available. There is probably a more elegant way to do this!
    """
    menu_bar = find_top_level_menubar()

    if menu_bar:
        if boostrap_engine_script:
            print("Starting %s ... %s" % (ENGINE_NAME, boostrap_engine_script))
            bootstrap()
        else:
            print(
                "SGTK_GAFFER_ENGINE_STARTUP not found. %s  won't be loaded!"
                % ENGINE_NAME
            )
    else:
        GafferUI.EventLoop.addIdleCallback(
            lambda: GafferUI.EventLoop.executeOnUIThread(check_ui_finished_loading)
        )


def bootstrap():
    engine_startup_path = os.environ.get("SGTK_GAFFER_ENGINE_STARTUP")
    if sys.version_info[0:2] >= (3, 4):
        import importlib

        engine_module_spec = importlib.util.spec_from_file_location(
            "sgtk_gaffer_engine_startup", engine_startup_path
        )
        engine_startup = importlib.util.module_from_spec(engine_module_spec)
        engine_module_spec.loader.exec_module(engine_startup)
    else:
        import imp

        engine_startup = imp.load_source(
            "sgtk_gaffer_engine_startup", engine_startup_path
        )

    # Fire up Toolkit and the environment engine when there's time.
    engine_startup.start_toolkit(application)


if boostrap_engine_script:
    menus_defs = GafferUI.ScriptWindow.menuDefinition(application)
    menus_defs.append("/Shotgun", {"subMenu": shotgunMenuCallable})

    # wait until Gaffer is not busy to check if the UI has finished loading
    GafferUI.EventLoop.addIdleCallback(
        lambda: GafferUI.EventLoop.executeOnUIThread(check_ui_finished_loading)
    )
