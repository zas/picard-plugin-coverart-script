# Local cover art scripting plugin for MusicBrainz Picard 3
#
# Copyright (C) 2026 Laurent Monin
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <https://www.gnu.org/licenses/>.

"""Adds a "script" matching mode to Picard's Local Files cover art provider.

The mode evaluates a tagger script for each file's metadata and uses the result
as a file name pattern (supporting ``*``, ``?`` and ``{a,b}`` wildcards) to find
matching local cover art files. It is registered through Picard's
``register_local_cover_art_mode`` extension point, so no changes to Picard core
are required.
"""

import os
import re

from picard.plugin3.api import (
    LocalCoverArtMode,
    Metadata,
    PluginApi,
    ScriptParser,
)

# picard.util.wildcards_to_regex_pattern is a stable, pure helper (no Picard
# state) that converts a shell-style file-name pattern into a regular
# expression, including the {a,b} alternation this mode relies on.
from picard.util import wildcards_to_regex_pattern


MODE_ID = 'coverart-script.script'

# The example pattern shown as the field placeholder and in the documentation.
EXAMPLE_PATTERN = '%albumartist% - %album%$if(%date%, [%date%],).{jpg,png}'


def _eval_script(script, metadata):
    """Evaluate a script and return its result for use as a file name pattern.

    Unlike script_to_filename(), the result is not sanitized as a file name:
    wildcard characters (``*``, ``?``, ``{``, ``}``, ``,``) are preserved so
    they can be interpreted as a pattern. Only path separators in metadata
    values are replaced, to keep matching limited to file names.
    """
    new_metadata = Metadata()
    for name in metadata:
        new_metadata[name] = [str(v).replace(os.sep, '_') for v in metadata.getall(name)]
    script = script.replace('\t', '').replace('\n', '')
    result = ScriptParser().eval(script, new_metadata)
    return result.replace('\x00', '')


def _pattern_to_re(pattern):
    """Compile a file name pattern (with wildcards) to a case-insensitive regex."""
    regex = wildcards_to_regex_pattern(
        pattern,
        allow_char_class=False,
        allow_alternation=True,
        anchored=True,
    )
    return re.compile(regex, re.IGNORECASE)


def queue_images(provider, script):
    """Queue local cover art whose file names match the script-built pattern.

    For each album directory the script is evaluated against a file's metadata
    to build a file name pattern, which is compiled to a regex and handed to the
    provider's ``find_local_images`` to yield the matching cover art images.
    """
    dirs_done = set()
    for file in provider.album.iterfiles():
        current_dir = os.path.dirname(file.filename)
        expected_filename = _eval_script(script, file.metadata)
        if not expected_filename:
            continue
        # Tracks of an album usually share metadata, so the evaluated pattern is
        # often identical across a directory. Walk each (dir, pattern) once.
        walk_key = (current_dir, expected_filename)
        if walk_key in dirs_done:
            continue
        dirs_done.add(walk_key)
        match_re = _pattern_to_re(expected_filename)
        for image in provider.find_local_images(current_dir, match_re):
            provider.queue_put(image)


def _make_playground_matcher(value, on_error):
    """Build a playground predicate: does a file name match the pattern?

    The playground has no metadata to evaluate a script against, so it tests the
    literal value as a wildcard file-name pattern.
    """
    if not value:
        return None
    try:
        pattern = _pattern_to_re(value)
    except re.error as e:
        on_error(str(e))
        return None
    return lambda line: bool(pattern.match(line))


def _show_documentation(parent):
    from picard.ui.options.scripting import ScriptingDocumentationDialog

    ScriptingDocumentationDialog.show_instance(parent=parent)


def enable(api: PluginApi) -> None:
    api.plugin_config.register_option(
        'script',
        EXAMPLE_PATTERN,
        title="Local cover art script",
        in_profile=True,
    )

    def get_script():
        return api.plugin_config['script']

    def set_script(value):
        api.plugin_config['script'] = value

    api.register_local_cover_art_mode(
        LocalCoverArtMode(
            id=MODE_ID,
            title="Script",
            description="Local cover art files match the file name produced by the following script:",
            note=(
                "The script is evaluated for each file's metadata; its result is used as a file name "
                "pattern. Wildcards are supported: * matches any number of characters, ? matches a "
                "single character, and {jpg,png} matches any of the comma separated alternatives. "
                "Matching is against the full file name including extension, and is case-insensitive. "
                "Sub-directories are searched, so the pattern is a file name, not a path."
            ),
            queue_images=queue_images,
            get_value=get_script,
            set_value=set_script,
            example=EXAMPLE_PATTERN,
            playground=True,
            make_matcher=_make_playground_matcher,
            show_doc=_show_documentation,
            doc_tooltip="Show scripting documentation",
        )
    )


def disable() -> None:
    pass
