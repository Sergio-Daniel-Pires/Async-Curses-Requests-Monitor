import asyncio
import random
import aiohttp
from aiohttp import ClientConnectorError

from utils import SendRequestsFront

async def make_request(url: str, front: SendRequestsFront):
    time = random.uniform(1, 1.7)
    await asyncio.sleep(time)
    index = front.send_box.update(f" ~  {url:<30}\t-")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    front.send_box.update(f" \u2714  {url:<30}\tOK", index=index)
                    return (url, 200)
                else:
                    front.logger.error(f"{url} {resp.status} {resp.reason}")
                    front.send_box.update(f" x  {url:<30}\t{resp.status} {resp.reason}", index=index)
                    return (url, resp.status)     
                 
    except ClientConnectorError:
        front.logger.error(f"{url:<30} 404 NOT FOUND")
        front.send_box.update(f" x  {url:<30}\t404 NOT FOUND", index=index)
        return (url, None)

    return (url, None)

async def safe_request(semaphore: asyncio.Semaphore, url: str, front: SendRequestsFront):
    async with(semaphore):
        return await make_request(url, front)

async def make_requests(service, name, front: SendRequestsFront):
    sites = [
        "https://www.google.com",
        "https://www.dummy.site.com",
        "https://www.facebook.com",
        "https://www.gmail.com",
        "https://web.whatsapp.com/",
        "https://www.mercadolivre.com",
        "https://www.another.dummy.com",
        "https://stackoverflow.com",
        "https://httpbin.org/post",
        "https://twitter.com"
    ]


    num_semaphore = 4
    sem = asyncio.Semaphore(num_semaphore)
    tasks = []
    front.logger.info("Preparando tasks assincronas")
    for url in sites:
        new_task = asyncio.create_task(safe_request(sem, url, front), name=url)
        tasks.append(asyncio.ensure_future(new_task))

    front.logger.warning(f"Foram criados {len(tasks)} Jobs, executando...")
    front.pbar_box.total = len(tasks)
    results = []
    for future_task in asyncio.as_completed(tasks):
        front.pbar_box.update(front.pbar_box.finished + 1, len(tasks))
        
        result = await future_task
        # TQDM Info
        info = [
            f"Elapsed Time:\t{front.pbar_box.elapsed}s",
            f"Remaining:\t{front.pbar_box.remaining}s",
            f"Avarage:\t{front.pbar_box.rate}s"
        ]
        stats = [
            f"Finished Jobs:\t{front.pbar_box.finished}",
            f"In Queue:\t{front.pbar_box.total - front.pbar_box.finished}",
            "",
            f"Service: {service}",
            f"Max threads:\t{num_semaphore}"
        ]
        front.info_box.update(info)
        front.stats_box.update(stats)
        results.append(result)
    
async def main():
    front = SendRequestsFront()
    requests = asyncio.create_task(make_requests('Get sites infos', 'files', front=front))
    auto_update = asyncio.create_task(front.auto_update())
    try:
        done, pending = await asyncio.wait({auto_update, requests}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        front.cleanup()

if __name__ == "__main__":
    asyncio.run(main())