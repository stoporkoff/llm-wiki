from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "software_factory.api:app",
        host=os.environ.get("FACTORY_HOST", "0.0.0.0"),
        port=int(os.environ.get("FACTORY_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
