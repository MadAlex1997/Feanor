"""No-op container job worker — example entrypoint for the base image."""
import asyncio
import sys

sys.path.insert(0, "/app")

from worker.sdk.client import WorkerClient
from worker.sdk.context import ExecutionContext


async def main() -> None:
    ctx = ExecutionContext()
    wc = WorkerClient(ctx)
    await wc.report_running()
    # Algorithm body here — no-op for base image
    result_ref = await wc.write_result({"ok": True, "inputs": ctx.inputs})
    await wc.report_succeeded(result_ref)


asyncio.run(main())
