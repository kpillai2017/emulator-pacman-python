"""ROM loader error messages: list every missing file and suggest the right --rom-set."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from roms import ROM_SETS, RomError, load_rom_set  # noqa: E402


def _names(rom_set):
    return [rom.file_name for rom in ROM_SETS[rom_set]["files"]]


class RomErrorMessageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _touch(self, names):
        for name in names:
            open(os.path.join(self.dir, name), "wb").close()

    def _error(self, rom_set):
        with self.assertRaises(RomError) as ctx:
            load_rom_set(rom_set, self.dir)
        return str(ctx.exception)

    def test_complete_other_set_suggests_switching(self):
        self._touch(_names("mspacman"))
        message = self._error("pacman")
        self.assertIn("'pacman.5e'", message)
        self.assertIn("All missing Pac-Man files: pacman.5e, pacman.5f", message)
        self.assertIn("complete Ms. Pac-Man ROM set: did you mean --rom-set mspacman?", message)

    def test_partial_other_set_lists_its_files(self):
        # Shared files, one Pac-Man-only file and part of the Ms. Pac-Man aux board.
        self._touch([n for n in _names("pacman") if n != "pacman.5f"])
        self._touch(["u5", "u6"])
        message = self._error("mspacman")
        self.assertIn("All missing Ms. Pac-Man files: 5e, 5f, u7", message)
        self.assertIn("contains Pac-Man files (pacman.5e): to run Pac-Man use --rom-set pacman.", message)

    def test_shared_files_alone_give_no_hint(self):
        shared = set(_names("pacman")) & set(_names("mspacman"))
        self._touch(sorted(shared))
        for rom_set in ROM_SETS:
            self.assertNotIn("--rom-set", self._error(rom_set))

    def test_single_missing_file_keeps_original_message(self):
        self._touch([n for n in _names("pacman") if n != "82s126.3m"])
        message = self._error("pacman")
        self.assertTrue(message.startswith("Could not locate the "))
        self.assertIn("'82s126.3m'", message)
        self.assertNotIn("All missing", message)
        self.assertNotIn("--rom-set", message)


if __name__ == "__main__":
    unittest.main()
