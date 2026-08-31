# End-to-end tests for the Local cover art scripting plugin.
#
# Run from the Picard source tree so the plugin API is importable, e.g.:
#   PYTHONPATH=/home/zas/src/picard:/home/zas/src/picard-plugin-coverart-script \
#     python -m pytest /home/zas/src/picard-plugin-coverart-script/test
#
# The tests use Picard's PicardTestCase so the configuration and Qt application
# are set up the same way as for Picard's own tests.

import importlib.util
import os
from pathlib import Path
from unittest.mock import Mock

from test.picardtestcase import PicardTestCase

# Importing the providers package registers the built-in regex mode.
import picard.coverart.providers  # noqa: F401
from picard.coverart.providers.local import CoverArtProviderLocal
from picard.extension_points.local_cover_art_modes import (
    ext_point_local_cover_art_modes,
    get_local_cover_art_mode,
    register_local_cover_art_mode,
)
from picard.metadata import Metadata


PLUGIN_DIR = Path(__file__).resolve().parent.parent


def _load_plugin_module():
    # Use a module name that is NOT under "picard.plugins." so the extension
    # point treats the registration as an internal (always-visible) one; this
    # avoids needing to wire up plugin-enabled UUID gating for the test.
    module_name = 'coverart_script_plugin_under_test'
    spec = importlib.util.spec_from_file_location(module_name, PLUGIN_DIR / '__init__.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakePluginConfig(dict):
    """Minimal stand-in for api.plugin_config backed by an in-memory dict."""

    def register_option(self, name, default, **kwargs):
        self.setdefault(name, default)


class _FakeApi:
    """Just enough of PluginApi for the plugin's enable() to run in tests."""

    def __init__(self):
        self.plugin_config = _FakePluginConfig()

    def register_local_cover_art_mode(self, mode):
        register_local_cover_art_mode(mode)


class CoverArtScriptPluginTest(PicardTestCase):
    def setUp(self):
        super().setUp()
        self.plugin = _load_plugin_module()
        self.plugin.enable(_FakeApi())
        self.addCleanup(self._unregister)

    def _unregister(self):
        ext_point_local_cover_art_modes.unregister(
            self.plugin.queue_images.__module__,
            lambda m: m.id == self.plugin.MODE_ID,
        )

    def _mode(self):
        # queue_images.__module__ is not a picard.plugins.* module here, so the
        # mode registers as an "internal" extension and is always visible.
        return get_local_cover_art_mode(self.plugin.MODE_ID)

    def test_mode_is_registered(self):
        mode = self._mode()
        self.assertIsNotNone(mode)
        self.assertEqual('Script', mode.title)
        self.assertTrue(mode.playground)
        self.assertIsNotNone(mode.make_matcher)
        self.assertIsNotNone(mode.show_doc)

    def test_value_roundtrip(self):
        mode = self._mode()
        mode.set_value('%album%.{jpg,png}')
        self.assertEqual('%album%.{jpg,png}', mode.get_value())

    def test_playground_matcher(self):
        mode = self._mode()
        matcher = mode.make_matcher('cover.{jpg,png}', lambda e: None)
        self.assertTrue(matcher('cover.jpg'))
        self.assertTrue(matcher('cover.png'))
        self.assertFalse(matcher('cover.txt'))

    def test_queue_images_matches_script_pattern(self):
        tmp = Path(self.mktmpdir())
        (tmp / 'The Beatles - Abbey Road.jpg').write_text('')
        (tmp / 'unrelated.jpg').write_text('')

        provider = CoverArtProviderLocal.__new__(CoverArtProviderLocal)
        provider._default_types = CoverArtProviderLocal._default_types
        provider._types_split_re = CoverArtProviderLocal._types_split_re
        provider._known_types = CoverArtProviderLocal._known_types

        f = Mock()
        f.filename = str(tmp / 'track01.mp3')
        f.metadata = Metadata({'albumartist': 'The Beatles', 'album': 'Abbey Road'})
        provider.album = Mock()
        provider.album.iterfiles.return_value = [f]
        queued = []
        provider.queue_put = queued.append

        mode = self._mode()
        mode.set_value('%albumartist% - %album%.*')
        mode.queue_images(provider, mode.get_value())

        names = sorted(os.path.basename(img.url.toLocalFile()) for img in queued)
        self.assertEqual(['The Beatles - Abbey Road.jpg'], names)
