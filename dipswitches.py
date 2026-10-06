# Python port of the C# DIPSwitches class and its dip-switches.json loader
import json
import os
import re

# Setting name -> (allowed values, default)
SETTINGS = {
    "CoinsPerGame": ((0, 1, 2, 3), 1),            # free play, 1C/1G, 1C/2G, 2C/1G
    "LivesPerGame": ((0, 1, 2, 3), 2),            # one, two, three, five
    "BonusScorePerExtraLife": ((0, 1, 2, 3), 0),  # 10,000 / 15,000 / 20,000 / none
    "Difficulty": ((0, 1), 1),                    # hard, normal
    "GhostNames": ((0, 1), 1),                    # alternate, normal
    "CabinetMode": ((0, 1), 1),                   # cocktail table, upright
}


class DIPSwitches:
    def __init__(self):
        for name, (_, default) in SETTINGS.items():
            setattr(self, name, default)

    def load(self, path: str) -> None:
        """Load settings from a JSON file. // comments are allowed, as in the C# version."""
        with open(path, "r") as f:
            text = f.read()
        # Strip // comments that are not inside a string
        text = re.sub(r'("(?:\\.|[^"\\])*")|//[^\n]*', lambda m: m.group(1) or "", text)
        values = json.loads(text)
        for name, value in values.items():
            if name not in SETTINGS:
                raise ValueError(f"Unknown DIP switch setting '{name}' in {path}")
            allowed, _ = SETTINGS[name]
            if value not in allowed:
                raise ValueError(f"Invalid value {value} for DIP switch '{name}' in {path}; allowed: {allowed}")
            setattr(self, name, value)

    @classmethod
    def from_file(cls, path):
        dips = cls()
        if path and os.path.isfile(path):
            dips.load(path)
        return dips

    def get_byte(self) -> int:
        """The byte read from 0x5080 (DSW1)."""
        return (self.CoinsPerGame                       # bits 0-1
                | (self.LivesPerGame << 2)              # bits 2-3
                | (self.BonusScorePerExtraLife << 4)    # bits 4-5
                | (self.Difficulty << 6)                # bit 6
                | (self.GhostNames << 7))               # bit 7

    def is_upright(self) -> bool:
        return self.CabinetMode == 1
