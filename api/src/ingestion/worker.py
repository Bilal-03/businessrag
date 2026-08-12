import asyncio

from src.ingestion.document_jobs import start_document_worker


async def main() -> None:
    queue = await start_document_worker()
    try:
        await asyncio.Event().wait()
    finally:
        await queue.stop()


if __name__ == "__main__":
    asyncio.run(main())
