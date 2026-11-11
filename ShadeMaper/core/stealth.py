import random
from time import time
from aiohttp.payload import payload_type
from fake_useragent import UserAgent
import urllib.parse
import re

class StealthEngine:
    def __init__(self) -> None:
        self.usgnt = UserAgent()

    def generate_randomheaders(self, referer=None):
        headers = {
            'User-Agent': self.usgnt.random,
            'Accept': "text/html, application/xhtml+xml,application/xml; q=0.9, image/avif ,image/webp ,*/* ;q=0.8",
            'Accept-Language': "en-US, en:q=0.5",
            'Referer': referer if referer else "https://google.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        return headers


class WafDetector:

    WAFSIGNS = {
        "CloudFlare": ['cf-ray', "cloudflare"],
        "AWS WAF": ["x-amz-cf-id", "awselb"],
        "Akami": ["x-akami-transformed", "akamighost"],
        "Incapsula": ["x-iinfo", "incapsula"],
        "Sucuri": ["x-sucuri-id", "sucuri/cloudproxy"]
    }

    @staticmethod
    async def wafsignerdetect(headers: dict, cookies: dict = None) -> str:
        headersstr = str(headers).lower()
        cookiesstr = str(cookies).lower()
        for waf_name, signs in WafDetector.WAFSIGNS.items():
            for sig in signs:
                if sig.lower() in headersstr or sig.lower() in cookiesstr:
                    return waf_name
        return "Неизвестная сигнатура"


class AdaptRatelimiter:
    def __init__(self, mndelay=0.1, mxdelay=0.5) -> None:
        self.delays = {}
        self.mndelay = mndelay
        self.mxdelay = mxdelay

    def check_delay(self, domain):
        return self.delays.get(domain, self.mndelay)

    def speed(self, domain, success):
        current = self.delays.get(domain, self.mndelay)
        if success:
            self.delays[domain] = max(self.mndelay, current * 0.9)
        else:
            self.delays[domain] = min(self.mxdelay, current * 1.5)


class Errorcircuitbreaker:
    def __init__(self):
        self.blocked_domains = {}
        self.duration = 60

    def blocked_checker(self, domain):
        if domain in self.blocked_domains:
            if time() < self.blocked_domains[domain]:
                return True
            del self.blocked_domains[domain]
        return False

    def report_error(self, domain, status_code):
        if status_code in [429, 503]:
            self.blocked_domains[domain] = time() + self.duration
            return True
        return False


class PayloadHider:
    def __init__(self) -> None:
        self.noise = ['/*--!*/', '%00', "/**/"]

    def hide(self, payload):
        hiden = ""
        for ch in payload:
            if ch == " ":
                hiden += random.choice(self.noise)
            hiden += ch
        return urllib.parse.quote(hiden)

    def double_encode(self, payload):
        return urllib.parse.quote(urllib.parse.quote(payload))

    def hexencode(self, payload):
        return "".join([f"%{ord(c):02x}" for c in payload])

    def unicodeencode(self, payload):
        return "".join([f"\\u{ord(c):04x}" for c in payload])

    def mixedencode(self, payload , mode="hex"):
          if mode == "double":
              return self.double_encode(payload)
          elif mode == "unicode":
                  return self.unicodeencode(payload)
          return self.hexencode(payload)
    def mixeddecode(self,payload):
        decoded = urllib.parse.unquote_plus(str(payload))
        if '%' in decoded:
            try:
                second_url_decode = urllib.parse.unquote(decoded)
                if second_url_decode != decoded:
                    decoded = second_url_decode
                    print(f"резудьтат декодирования {decoded}")
            except Exception as e:
                print(f"ошибка  в декодировании {e}")
                pass
        if "\\u" in decoded or r"\u" in decoded:
          try:
             decoded = decoded.encode('utf-8').decode("unicode_escape")

          except Exception:
              pass
        if "%"   in decoded:
            try:
                hexclean = decoded.replace("%", "")
                decoded =  bytes.fromhex(hexclean).decode('utf-8')
            except Exception as e:
               pass
        for n in self.noise:
            if n in decoded:
               decoded = decoded.replace(n, " ")
        decoded = re.sub(r'\s+', ' ', decoded).strip()
        return decoded
