import curses
import asyncio
import logging
from tqdm import tqdm
from datetime import datetime
import random

from utils import SendRequestsFront

async def make_request(file: str):
    time = random.uniform(1, 7)
    await asyncio.sleep(time)
    if file[-1] in ("3", "9"):
        raise Exception("404 Not Found")
    else:
        return True

async def safe_request(semaphore: asyncio.Semaphore, file: str, front: SendRequestsFront):
    async with(semaphore):
        index = front.send_box.update(f" ~  {file}\t-")
        try:
            result = await make_request(file)
            front.send_box.update(f" \u2714  {file}\tOK", index=index)
        except Exception as err:
            front.logger.error(f"{file} {err}")
            front.send_box.update(f" x  {file}\t{err}", index=index)

async def make_requests(service, name, front: SendRequestsFront):
    files = [f"{name}-{x}" for x in range(15)]
    num_semaphore = 4
    sem = asyncio.Semaphore(num_semaphore)
    tasks = []
    for file in files:
        new_task = asyncio.create_task(safe_request(sem, file, front), name=file)
        tasks.append(asyncio.ensure_future(new_task))

    front.pbar_box.total = len(tasks)
    c_tqdm = tqdm(total=len(tasks), disable=True)
    for future_task in asyncio.as_completed(tasks):
        front.pbar_box.update(front.pbar_box.finished + 1, len(tasks))
        
        result = await future_task
        # TQDM Info
        c_tqdm.update(1)
        rate = c_tqdm.format_dict["rate"] 
        rate = rate if rate else 0
        remaining = (c_tqdm.total - c_tqdm.n) / rate if rate and c_tqdm.total else 0
        info = [
            f"Elapsed Time:\t{c_tqdm.format_dict['elapsed']}",
            f"Remaining:\t{remaining}",
            f"Avarage:\t{rate}"
        ]
        front.info_box.update(info)

async def main():
    front = SendRequestsFront()
    requests = asyncio.create_task(make_requests('Service tasks', 'files', front=front))
    auto_update = asyncio.create_task(front.auto_update())
    try:
        done, pending = await asyncio.wait({auto_update, requests}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        front.cleanup()

if __name__ == "__main__":
    asyncio.run(main())