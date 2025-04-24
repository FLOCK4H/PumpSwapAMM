import multiprocessing as mp
import time
from solders.keypair import Keypair # type: ignore

from multiprocessing.queues import Queue as MPQueue
from multiprocessing.synchronize import Event as MPEvent
try: from colors import *;
except: from .colors import *;

def _worker(
    suffix: str,
    stop_event: MPEvent,
    out_q: MPQueue,
) -> None:
    while not stop_event.is_set():
        kp = Keypair()
        addr = str(kp.pubkey())
        if addr.endswith(suffix):
            out_q.put((addr, kp))
            stop_event.set()
            return

def grind_custom_mint(suffix: str = "pump") -> Keypair:
    n_workers = mp.cpu_count()
    stop_event = mp.Event()
    out_q = mp.Queue()

    cprint(f"[*] Spinning up {n_workers} workers to grind for ‘…{suffix}’")
    start = time.time()

    procs = []
    for _ in range(n_workers):
        p = mp.Process(target=_worker, args=(suffix, stop_event, out_q), daemon=True)
        p.start()
        procs.append(p)

    addr, secret = out_q.get()
    elapsed = time.time() - start

    stop_event.set()
    for p in procs:
        p.terminate()
        p.join()

    cprint(f"[+] Found {addr} in {elapsed:.1f}s")
    return secret

if __name__ == "__main__":
    kp = grind_custom_mint("pump")
    cprint("PUBKEY:", kp.pubkey())
