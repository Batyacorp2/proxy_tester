from typing import Optional
import json, csv, sys, time, asyncio
import httpx
import typer
from rich.progress import Progress

app = typer.Typer(help="Mass proxy tester (HTTP/HTTPS/SOCKS)")

async def _probe(proxy: str, target: str, timeout: float) -> dict:
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(proxies=proxy, timeout=timeout) as client:
            r = await client.get(target)
        dt = time.perf_counter() - t0
        return {"proxy": proxy, "ok": r.status_code < 400, "status": r.status_code, "latency_ms": int(dt*1000)}
    except Exception as e:
        dt = time.perf_counter() - t0
        return {"proxy": proxy, "ok": False, "error": str(e), "latency_ms": int(dt*1000)}

@app.command("check")
def check(
    input: str = typer.Option(..., help="Файл со списком прокси (по одному в строке, схема обязательна: http://, https://, socks5://)"),
    target: str = typer.Option("https://example.com", help="URL для проверки"),
    concurrency: int = typer.Option(200, help="Одновременных запросов"),
    timeout: float = typer.Option(5.0, help="Таймаут, сек"),
    output: Optional[str] = typer.Option(None, help="Путь для JSON/CSV. По расширению определяется формат."),
):
    with open(input, "r", encoding="utf-8") as f:
        proxies = [line.strip() for line in f if line.strip()]

    async def runner():
        results = []
        sem = asyncio.Semaphore(concurrency)
        async def task(p):
            async with sem:
                return await _probe(p, target, timeout)
        with Progress() as progress:
            t = progress.add_task("Checking proxies", total=len(proxies))
            tasks = [asyncio.create_task(task(p)) for p in proxies]
            for coro in asyncio.as_completed(tasks):
                res = await coro
                results.append(res)
                progress.update(t, advance=1)
        return results

    results = asyncio.run(runner())

    if not output:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        raise typer.Exit()

    if output.lower().endswith(".json"):
        with open(output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    elif output.lower().endswith(".csv"):
        fieldnames = sorted({k for r in results for k in r.keys()})
        with open(output, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
    else:
        print("Unsupported output format. Use .json or .csv", file=sys.stderr)
        raise typer.Exit(code=2)
