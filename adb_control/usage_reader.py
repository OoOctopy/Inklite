"""Dumpsys formats vary by Android/OEM. Unknown or ambiguous records are never blocked."""
from dataclasses import dataclass
import re
from .adb_client import AdbError

RECORD = re.compile(r"\bu(?P<user>\d+)\s+(?P<package>[A-Za-z][\w]*(?:\.[A-Za-z][\w]*)+)/[.\w$]+")


@dataclass(frozen=True)
class ForegroundApp:
    package: str
    user: int


def parse_foreground(output, markers):
    for marker in markers:
        records = set()
        for line in output.splitlines():
            if marker in line:
                match = RECORD.search(line)
                if match:
                    records.add(ForegroundApp(match["package"], int(match["user"])))
        if len(records) == 1:
            return records.pop()
        if len(records) > 1:
            raise AdbError("Multiple resumed/focused activities; foreground is ambiguous (multi-window/display).")
    return None


class UsageReader:
    def __init__(self, adb):
        self.adb = adb

    def foreground(self):
        output = self.adb.shell("dumpsys", "activity", "activities")
        app = parse_foreground(output, ("topResumedActivity", "mTopResumedActivity", "mResumedActivity", "ResumedActivity:"))
        if app is not None:
            return app
        output = self.adb.shell("dumpsys", "window", "windows")
        # mCurrentFocus=null on lock screens: do not use a stale mFocusedApp.
        return parse_foreground(output, ("mCurrentFocus",))

    def usage_stats(self):
        """Return raw diagnostics; OEM formats do not promise portable duration statistics."""
        return self.adb.shell("dumpsys", "usagestats")
