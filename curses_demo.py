import curses
import asyncio

from utils import SendRequestsFront

async def make_request():
    await asyncio.sleep(3)
    return

async def safe_request(semaphore: asyncio.Semaphore, file: str):
    async with(semaphore):
        return await make_request()

async def make_requests(service, name, front: SendRequestsFront):
    files = [f"{name}-{x}" for x in range(30)]
    num_semaphore = 2
    sem = asyncio.Semaphore(num_semaphore)
    tasks = []
    for file in files:
        tasks.append(asyncio.ensure_future(safe_request(sem, file)))
        front.send_box.update(file)

    front.pbar_box.total = len(tasks)
    for future_task in asyncio.as_completed(tasks):
        front.pbar_box.update(front.pbar_box.finished + 1, len(tasks))
        
        result = await future_task

async def main():
    front = SendRequestsFront()
    requests = asyncio.create_task(make_requests('Service tasks', 'files', front=front))
    auto_update = asyncio.create_task(front.auto_update())
    try:
        done, pending = await asyncio.wait({auto_update, requests}, return_when=asyncio.FIRST_COMPLETED)

        if done in pending:
            print("Cabou")
            print(done)
            print(pending)

    except Exception as ex:
       print(str(ex))
    finally:
        front.cleanup()

if __name__ == "__main__":
    asyncio.run(main())