"""Keep the write gate alive independently of synchronous checkpoint work."""
from fc27_academy.fsutil import replace_retry
import atexit, os, threading, time
from pathlib import Path

class EngineLease:
    def __init__(self, path, owner_alive=lambda: True, interval=2, log=None):
        self.path=Path(path); self.owner_alive=owner_alive; self.interval=interval
        self.stop=threading.Event(); self.thread=None
        # v1.24.13: report renewals that fail or arrive late (the game-side script
        # treats a lease older than 8 s as "bridge gone").
        self.log=log or (lambda msg: None); self.last_ok=None; self.failures=0
    def refresh(self):
        tmp=self.path.with_suffix('.heartbeat.tmp')
        tmp.write_text(str(int(time.time())),encoding='utf-8')
        replace_retry(tmp,self.path)
    def start(self):
        self.refresh()
        self.last_ok=time.monotonic()
        def run():
            while not self.stop.wait(self.interval):
                if not self.owner_alive(): break
                try:
                    self.refresh()
                except OSError as exc:
                    self.failures+=1
                    if self.failures in (1,3) or self.failures%15==0:
                        self.log(f'FC27AE_LEASE_WRITE_FAILED consecutive={self.failures} since_last_ok_s={time.monotonic()-self.last_ok:.1f} detail={exc}')
                    continue
                now=time.monotonic(); gap=now-self.last_ok
                if self.failures or gap>=5.0:
                    self.log(f'FC27AE_LEASE_RENEWED gap_s={gap:.1f} after_failures={self.failures}')
                self.failures=0; self.last_ok=now
            self.path.unlink(missing_ok=True)
        self.thread=threading.Thread(target=run,name='FC27AE-Heartbeat',daemon=True)
        self.thread.start(); atexit.register(self.close)
    def close(self):
        self.stop.set()
        if self.thread and self.thread is not threading.current_thread(): self.thread.join(timeout=3)
        self.path.unlink(missing_ok=True)
