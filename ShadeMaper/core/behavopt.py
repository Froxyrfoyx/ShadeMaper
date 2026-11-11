import asyncio
import random
import time

class BehavOptimize:
    def __init__(self, delay=1.0, min_assts=2):
        self.delay = delay
        self.min_assets = min_assts
        self.assets = ["/favicon.ico", '/css/style.css', "/js/main.js", '/assets/logo.png']

    def jitter_delay(self):
        return random.expovariate(1.0 / self.delay)

    async def opensession(self, requestfunc):
        for _ in range(self.min_assets):
            asset = random.choice(self.assets)
            await requestfunc(asset)
            await asyncio.sleep(0.3)

    async def waitb4action(self):
        delay = self.jitter_delay()
        await asyncio.sleep(delay)
