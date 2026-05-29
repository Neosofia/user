import asyncio
import httpx
import time
import statistics
import os
from dotenv import load_dotenv

# Change to absolute load of .env file from the repo root
load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
TOKEN = os.getenv("DEV_JWT_TOKEN", "").strip('"')

URL = "http://localhost:8018/api/v1/documents/d1"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
    "X-Forwarded-Proto": "https"
}

sem = asyncio.Semaphore(16)

async def fetch(client):
    async with sem:
        start = time.perf_counter()
        try:
            res = await client.get(URL, headers=HEADERS)
            status = res.status_code
        except Exception as e:
            status = 0
        end = time.perf_counter()
        return end - start, status

async def main():
    clients_count = 32
    calls_per_client = 1000
    requests_to_make = clients_count * calls_per_client
    
    sem = asyncio.Semaphore(clients_count)

    async def fetch(client):
        async with sem:
            start = time.perf_counter()
            try:
                res = await client.get(URL, headers=HEADERS)
                status = res.status_code
            except Exception as e:
                status = 0
            end = time.perf_counter()
            return end - start, status

    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=clients_count, max_keepalive_connections=clients_count)) as client:
        start_overall = time.perf_counter()
        tasks = [fetch(client) for _ in range(requests_to_make)]
        results = await asyncio.gather(*tasks)
        end_overall = time.perf_counter()
        
    latencies = [r[0] * 1000 for r in results]
    codes = [r[1] for r in results]
    
    print(f"Total time for {requests_to_make} requests ({clients_count} concurrency): {end_overall - start_overall:.2f}s")
    print(f"RPS (Requests Per Second): {requests_to_make / (end_overall - start_overall):.2f}")
    print(f"Status codes: {set(codes)}")
    
    if latencies:
        print(f"\nMetrics (ms) [n={len(latencies)}]:")
        print(f"  Mean:   {statistics.mean(latencies):.2f} ms")
        print(f"  Median: {statistics.median(latencies):.2f} ms")
        print(f"  Min:    {min(latencies):.2f} ms")
        print(f"  Max:    {max(latencies):.2f} ms")

if __name__ == "__main__":
    asyncio.run(main())