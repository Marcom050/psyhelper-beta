from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4)

def run_task(func, *args, **kwargs):
    return _executor.submit(func, *args, **kwargs)
