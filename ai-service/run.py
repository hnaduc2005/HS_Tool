"""Run Uvicorn on a selector event loop for Psycopg on Windows."""

import asyncio
import selectors

import uvicorn


def main() -> None:
    server = uvicorn.Server(uvicorn.Config("app.main:app", host="127.0.0.1", port=8000))
    with asyncio.Runner(loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector())) as runner:
        runner.run(server.serve())


if __name__ == "__main__":
    main()
