from __future__ import annotations

import os

from .server import run_server


def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    run_server(host=host, port=port)


if __name__ == "__main__":
    main()

