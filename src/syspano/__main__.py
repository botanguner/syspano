"""syspano paketinin giriş noktası: `python3 -m syspano`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
