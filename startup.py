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
import sys

import sgtk
from sgtk.platform import SoftwareLauncher, SoftwareVersion, LaunchInformation


__author__ = "Diego Garcia Huerta"
__contact__ = "https://www.linkedin.com/in/diegogh/"


ENGINE_NAME = "tk-gaffer"
APPLICATION_NAME = "Gaffer"


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
    _GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    _GetShortPathNameW.restype = wintypes.DWORD

    def get_short_path_name(long_name):
        """
        Gets the short path name of a given long path.
        http://stackoverflow.com/a/23598461/200291
        """
        output_buf_size = 0
        while True:
            output_buf = ctypes.create_unicode_buffer(output_buf_size)
            needed = _GetShortPathNameW(long_name, output_buf, output_buf_size)
            if output_buf_size >= needed:
                return output_buf.value
            else:
                output_buf_size = needed


class GafferLauncher(SoftwareLauncher):
    """
    Handles launching Gaffer executables. Automatically starts up
    a tk-gaffer engine with the current context in the new session
    of Gaffer.
    """

    # Named regex strings to insert into the executable template paths when
    # matching against supplied versions and products. Similar to the glob
    # strings, these allow us to alter the regex matching for any of the
    # variable components of the path in one place
    COMPONENT_REGEX_LOOKUP = {"version": r"\d+.\d+.\d+.\d+", "platform": r"\w+"}

    # This dictionary defines a list of executable template strings for each
    # of the supported operating systems. The templates are used for both
    # globbing and regex matches by replacing the named format placeholders
    # with an appropriate glob or regex string.

    EXECUTABLE_TEMPLATES = {
        "darwin": ["$GAFFER_BIN", "/opt/Gaffer-{version}-{platform}/bin/gaffer"],
        "win32": [
            "$GAFFER_BIN",
            "%programfiles%/gaffer-{version}-{platform}/bin/gaffer.bat",
        ],
        "linux2": ["$GAFFER_BIN", "/opt/Gaffer-{version}-{platform}/bin/gaffer"],
    }

    @property
    def minimum_supported_version(self):
        """
        The minimum software version that is supported by the launcher.
        """
        return "0.53.6.0"

    def prepare_launch(self, exec_path, args, file_to_open=None):
        """
        Prepares an environment to launch Gaffer in that will automatically
        load Toolkit and the tk-gaffer engine when Gaffer starts.

        :param str exec_path: Path to Gaffer executable to launch.
        :param str args: Command line arguments as strings.
        :param str file_to_open: (optional) Full path name of a file to open on
                                            launch.
        :returns: :class:`LaunchInformation` instance
        """
        required_env = {}

        # Run the engine's init.py file when Gaffer starts up
        startup_path = os.path.join(self.disk_location, "startup", "init.py")

        # Prepare the launch environment with variables required by the
        # classic bootstrap approach.
        self.logger.debug("Preparing Gaffer Launch via Toolkit Classic methodology ...")

        # Run the engine's init.py file when the application  starts up
        startup_path = os.path.join(self.disk_location, "startup", "init.py")

        required_env["SGTK_GAFFER_ENGINE_STARTUP"] = startup_path.replace("\\", "/")

        gaffer_startup_path = os.path.join(self.disk_location, "startup", "gaffer")
        sgtk.util.append_path_to_env_var("GAFFER_STARTUP_PATHS", gaffer_startup_path)

        required_env["SGTK_GAFFER_MODULE_PATH"] = sgtk.get_sgtk_module_path().replace(
            "\\", "/"
        )

        required_env["SGTK_ENGINE"] = ENGINE_NAME
        required_env["SGTK_CONTEXT"] = sgtk.context.serialize(self.context)

        if file_to_open:
            # Add the file name to open to the launch environment
            required_env["SGTK_FILE_TO_OPEN"] = file_to_open

        args = ""

        if sys.platform == "win32":
            exec_path = get_short_path_name(exec_path)

        return LaunchInformation(exec_path, args, required_env)

    def _icon_from_engine(self):
        """
        Use the default engine icon as gaffer does not supply
        an icon in their software directory structure.

        :returns: Full path to application icon as a string or None.
        """

        # the engine icon
        engine_icon = os.path.join(self.disk_location, "icon_256.png")
        return engine_icon

    def scan_software(self):
        """
        Scan the filesystem for gaffer executables.

        :return: A list of :class:`SoftwareVersion` objects.
        """
        self.logger.debug("Scanning for Gaffer executables...")

        supported_sw_versions = []
        for sw_version in self._find_software():
            (supported, reason) = self._is_supported(sw_version)
            if supported:
                supported_sw_versions.append(sw_version)
            else:
                self.logger.debug(
                    "SoftwareVersion %s is not supported: %s" % (sw_version, reason)
                )

        return supported_sw_versions

    def _find_software(self):
        """
        Find executables in the default install locations.
        """

        # all the executable templates for the current OS
        executable_templates = self.EXECUTABLE_TEMPLATES.get(sys.platform, [])

        # all the discovered executables
        sw_versions = []

        # Here we account for extra arguments passed to the blender command line
        # this allows a bit of flexibility without having to fork the whole
        # engine just for this reason.
        # Unfortunately this cannot be put in the engine.yml as I would like
        # to because the engine class has not even been instantiated yet.
        extra_args = os.environ.get("SGTK_GAFFER_CMD_EXTRA_ARGS")

        for executable_template in executable_templates:
            executable_template = os.path.expanduser(executable_template)
            executable_template = os.path.expandvars(executable_template)

            self.logger.debug("Processing template %s.", executable_template)

            executable_matches = self._glob_and_match(
                executable_template, self.COMPONENT_REGEX_LOOKUP
            )

            # Extract all products from that executable.
            for (executable_path, key_dict) in executable_matches:

                # extract the matched keys form the key_dict (default to None
                # if not included)
                executable_version = key_dict.get("version")

                args = []
                if extra_args:
                    args.append(extra_args)

                sw_versions.append(
                    SoftwareVersion(
                        executable_version,
                        APPLICATION_NAME,
                        executable_path,
                        icon=self._icon_from_engine(),
                        args=args,
                    )
                )

        return sw_versions
