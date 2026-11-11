import asyncio
import concurrent.futures
from enum import verify
from logging import log
import random
import re
from asyncio.events import get_event_loop
from socket import timeout
from time import time
from urllib.parse import urljoin, urlparse
from fake_useragent import fake
from jinja2 import ext
import redis.asyncio as redis
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession, get, query
from yaml import emit
from core.analyzer import Analyzer
from core.config import ConfigsettingManager
from core.graphmanager import GraphManager
from core.stealth import (AdaptRatelimiter, Errorcircuitbreaker,
                          StealthEngine, WafDetector , PayloadHider)
from core.behavopt import BehavOptimize
from core.domscaner import DomScaner
from core.dscan import Dpredictor, PhantomNodedetector
from core.RSD import ResonanceDetector
from logger import AsyncLogger
from  urllib.parse import urlparse, parse_qsl, urlencode, urlunparse, parse_qs

import logger
stealth = StealthEngine()
breaker = Errorcircuitbreaker()
behav = BehavOptimize()
doms = DomScaner()
rsd =  ResonanceDetector()
pldhd = PayloadHider()
class WebantulaCrawler:
    def __init__(self, base_url: str, manager, signals, analyzer: Analyzer):
        self.headers = stealth.generate_randomheaders()
        self.settings = ConfigsettingManager()
        self.logger = AsyncLogger(filename="shademaper.log")
        self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=4)
        self.manager = GraphManager()
        self.breaker = breaker
        self.behav = BehavOptimize()
        self.dom = DomScaner()
        self.rsd = ResonanceDetector()
        self.dp =  Dpredictor(self.settings)
        self.pnd = PhantomNodedetector(self.settings)
        self.pld = pldhd
        self.signals = signals
        self.analyzer = analyzer
        self.ratelimiter = AdaptRatelimiter()
        self.semaphore = asyncio.Semaphore(value=5)
        self.base_url = base_url
        self.r = redis.Redis(host='127.0.0.1', port=6379,  protocol=2, decode_responses=True, health_check_interval=10, socket_keepalive=True,retry_on_timeout=True, retry_on_error=[redis.ConnectionError, redis.TimeoutError])
        self.fuzz_config = self.settings.get('fuzz_engine', {})
        self.vectors = self.settings.get('vectors', {
            'generic': ["/.env", "/config.php", "/.git/config", "/backup.zip"],
            'cms': {'wordpress': ["/wp-config.php", "/wp-login.php"]}
        })
        self.target_domain = urlparse(base_url).netloc
        self.skip_exts = {'.png', '.jpg', '.jpeg', '.gif', '.css', '.js', '.woff', '.svg', '.pdf', '.ico'}
    async def getTechrType(self, session, url):
        if "wp-" in url: return "wordpress"
        if "artisan" in url: return "laravel"
        return "generic"
    def is_valid_locale(self,url: str, base_url: str) -> bool:
            try:
                parsed_url = urlparse(url)
                path = parsed_url.path.lower()
                locale_pattern = re.compile(r'\/([a-z]{2}-[a-z]{2}|[a-z]{2})\/')
                match = locale_pattern.search(path)
                if match:
                    detected_locale = match.group(0)
                    if detected_locale in base_url.lower():
                        return True
                    if detected_locale in ["/en/", "/en-us/"]:
                        return True
                    return False
                return True
            except Exception:
                return False
    async def get_links(self, session, url):
        try:
            response = await session.get(url, headers=self.headers, impersonate="chrome120",timeout=10)
            waf = await WafDetector.wafsignerdetect(headers=response.headers,  cookies=response.cookies)
            soup = BeautifulSoup(response.text, 'html.parser')
            links = set()
            for a in soup.find_all('a', href=True):
                href = a.get('href')
                if href:
                    full_url = urljoin(url, str(href))
                    if self.is_validTarget(full_url) and self.is_valid_locale(full_url, self.base_url):
                        links.add(full_url)
            return links,waf
        except Exception as e:
            print(f'Ошибка в подборе ссылок {e}')
            return set(),None

    async def run_worker(self, session:AsyncSession) -> None:
           async with self.semaphore:
               while True:
                   data = await self.r.blpop("task_queue", timeout=5)
                   if not data:
                       break
                   url = data[1]
                   print(f"Дебаг обработка {url}")
                   self.logger.log("info" ,f"Обработка {url}" )
                   await self.behav.waitb4action()
                   if await self.r.sadd("visited", url) == 0:
                       continue
                   if self.breaker.blocked_checker(url):
                       continue
                   tech = await self.getTechrType(session, url)
                   try:
                       loop = asyncio.get_running_loop()
                       score = await loop.run_in_executor(self.executor, self.analyzer.calc_score, url)
                       new_links, waf_name = await self.get_links(session, url)
                       is_soft_404 = False
                       if len(new_links) == 0:
                           url_lower = url.lower()
                           if url_lower.startswith(('javascript:', 'mailto:', 'tel:')):
                               return

                           is_static_file = any(url_lower.endswith(ext) for ext in ['.sql', '.zip', '.txt', '.gz', '.tar', '.php', '.env', '.config', '.bak', '.xml'])
                           if not is_static_file:
                               print("Подгружаем дом сканер")
                               self.logger.log("warn", "Подгружаем DOM  сканер для SPA  приложения")
                               dom_content = await self.dom.render_page(url)
                               if dom_content:
                                   hiddenDomQuery = await self.dom.monke_clicks(
                                       context=self.dom.browser_context,
                                       content=dom_content,
                                       base_url=url
                                   )
                                   print(f"Скрытые квери параметры {hiddenDomQuery}")
                                   self.logger.log("warn", f"скрытые квери параметры {hiddenDomQuery}")
                                   if hiddenDomQuery:
                                       p = urlparse(url)
                                       base_query = parse_qs(p.query)
                                       for k, v in hiddenDomQuery.items():
                                           q = base_query.copy()
                                           q[k] = v
                                           generated_url = urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q, doseq=True), p.fragment))
                                           new_links.add(generated_url)
                                   dom_lower = dom_content.lower()
                                   soup = BeautifulSoup(dom_lower, "html.parser")
                                   page_title = soup.title.string.lower() if soup.title and soup.title.string else ""
                                   if any(err in page_title for err in ["404", "not found", "error", "ошибка", "не найдена", "denied", "blocked"]):
                                       is_soft_404 = True
                                   else:
                                       for a in soup.find_all("a", href=True):
                                           href = a.get("href")
                                           if href:
                                               full_url = urljoin(url, str(href))
                                               if self.is_validTarget(full_url) and self.is_valid_locale(full_url, self.base_url):
                                                   new_links.add(full_url)
                               else:
                                   is_soft_404 = True
                           else:
                               is_soft_404 = True
                       if not is_soft_404 and any(ext in url.lower() for ext in ['.sql', '.zip', '.env', '.php', '.config', 'backup', '.bak']):
                           try:
                               direct_resp = await session.get(url, timeout=4)
                               if direct_resp.status == 200:
                                   content_type = direct_resp.headers.get('Content-Type', '').lower()
                                   body_sample = direct_resp.text.strip()
                                   body_sample_lower = body_sample.lower()
                                   if any(ext in url.lower() for ext in ['.zip', '.sql', '.tar', '.gz', '.bak']):
                                       if "html" in content_type or "json" in content_type or body_sample_lower.startswith("<!doctype") or body_sample_lower.startswith("<html"):
                                           is_soft_404 = True
                                   if ".env" in url.lower():
                                       if "html" in content_type or body_sample_lower.startswith("<!doctype") or body_sample_lower.startswith("<html"):
                                           is_soft_404 = True
                                       elif len(body_sample) > 0 and not any(re.search(r'^[A-Z0-9_]+=', line.strip()) for line in body_sample.split('\n') if line.strip() and not line.strip().startswith('#')):
                                           is_soft_404 = True
                           except Exception:
                               is_soft_404 = True
                       if is_soft_404 or (len(new_links) == 0 and any(ext in url.lower() for ext in ['.sql', '.zip', '.env', '.php', '.config', 'backup'])):
                           score = 0
                       status = 'interesting' if score >= 80 else 'safe'
                       domain = urlparse(url).netloc
                       if waf_name and waf_name != "Неизвестная сигнатура":
                           print(f" ! обнаружен {waf_name} на {url}, включаю лимит скорости")
                           self.logger.log("warn", f"Обнаружен {waf_name} на {url} включаю лимит скорости...")
                           self.ratelimiter.speed(domain, success=False)
                           status = "защищен waf"
                           score = 0
                       await self.manager.add_node(url, label=url, score=score, status=status)
                       await asyncio.sleep(self.ratelimiter.check_delay(domain))
                       print(f"ссылки {len(new_links)}")
                       self.logger.log("info",f"ссылки {len(new_links)}" )
                       for link in new_links:
                           if await self.r.sismember('visited', link):
                               continue
                           parsed_link = urlparse(link)
                           target_domain = urlparse(self.base_url).netloc
                           if parsed_link.netloc == "" or target_domain in parsed_link.netloc:
                               await self.manager.add_node(link, label=link)
                               await self.manager.add_edge(url, link)
                               await self.r.rpush('task_queue', link)
                       if score >= 50:
                           print(score)
                           phantom_paths = self.pnd.hidden_pathsearcher(url, list(new_links))
                           predicted_path = self.dp.predict_path(url)
                           for hiden_path in phantom_paths.union(predicted_path):
                               hiden_lower = hiden_path.lower()
                               if any(hiden_lower.endswith(ext) for ext in ['.sql', '.zip', '.txt', '.gz', '.tar', '.php', '.env', '.config']) and any(x in url.lower() for x in ['.sql', '.zip', '.txt', '.gz', '.tar', '.php', '.env', '.config']):
                                   continue
                               if not await self.r.sismember("visited", hiden_path):
                                   parsed_link = urlparse(hiden_path)
                                   target_domain = urlparse(self.base_url).netloc
                                   if parsed_link.netloc == "" or target_domain in parsed_link.netloc:
                                       await self.manager.add_node(hiden_path, label=hiden_path)
                                       await self.manager.add_edge(url, hiden_path)
                                       await self.r.rpush("task_queue", hiden_path)

                       confirmed_vulnerabilities = await self.check_node(session, url, tech)
                       print(confirmed_vulnerabilities)
                       if confirmed_vulnerabilities:
                        status = "vulnerable"
                        score = 100
                        await self.manager.add_node(url, label=url, score=score, status=status)
                        for vuln in confirmed_vulnerabilities:
                          v_url = vuln.get('url')
                          v_type = vuln.get('vuln_type', 'VULN')
                          v_score = vuln.get('score', 100)
                          if v_url:
                             parsed_vuln = urlparse(v_url)
                             print(f"Уявзимость в {parsed_vuln}")
                             self.logger.log("critical", f"уязвимость в {parsed_vuln}")
                             query_display = parsed_vuln.query[:30] if parsed_vuln.query else "payload"
                             await self.manager.add_node(v_url, label=f"⚠️ [{v_type}] {query_display}...", score=v_score, status="vulnerable")
                             await self.manager.add_edge(url, v_url)
                             self.analyzer.calc_score(v_url)
                             attack_path = self.manager.find_shorttestpath(self.base_url, v_url)
                             if attack_path:
                                           print(f" attack_path ВЕКТОР НАЙДЕН: {' ➔ '.join(attack_path)}")
                   except Exception as e:
                       print(f"Произошла ошибка {e}")
                   finally:
                       try:
                           await self.manager.save(self.base_url)
                       except Exception as e_save:
                           print(f"Ошибка сохранения карты: {e_save}")

    def is_validTarget(self, url: str) -> bool:
        parsed = urlparse(url)
        if self.target_domain not in parsed.netloc and parsed.netloc != "":
            return False
        if any(url.lower().endswith(ext) for ext in self.skip_exts):
            return False
        return True

    async def check_node(self, session:AsyncSession, url, tech):
        paths = list(self.vectors.get('generic', []))
        if isinstance(self.vectors.get(tech), list):
            paths += self.vectors.get(tech, [])
        elif isinstance(self.vectors.get(tech), dict):
            for sub_paths in self.vectors.get(tech, {}).values():
                paths += sub_paths
        parsed = urlparse(url)
        params = parsed.query.split('&') if parsed.query else []
        tasks = []
        path_matchers = self.fuzz_config.get('path_scan', {})
        for path in paths:
            tasks.append(self.probe_path(session, url, path, path_matchers))
        fuzz_vectors_config = self.fuzz_config.get('fuzz_vectors', {})
        if params and fuzz_vectors_config:
            for pman in params:
                if '=' in pman:
                    pname_parts = pman.split('=')
                    pname = pname_parts[0]
                    for category, config in fuzz_vectors_config.items():
                        payloads = config.get('payloads', [])
                        matchers = config.get('matchers', {})
                        for pl in payloads:
                            obfuscated_pl = self.pld.mixedencode(pl)
                            new_query = parsed.query.replace(f"{pman}", f"{pname}={obfuscated_pl}")
                            new_url = parsed._replace(query=new_query).geturl()
                            tasks.append(self.probe_fuzz(session, url, new_url, category, matchers))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    async def probe_path(self, session:AsyncSession, url, path, path_matchers):
                try:
                    if any(url.lower().endswith(ext) for ext in ['.sql', '.env', '.zip', '.txt', '.php', '.html', '.gz', '.tgz']):
                        return None
                    test_url = f"{url.rstrip('/')}/{path.lstrip('/')}"
                    pathl = path.lower()
                    resp = await session.get(test_url, timeout=4, allow_redirects=False)
                    status_code = int(resp.status_code)
                    body_bytes =  resp.content
                    body_raw = body_bytes.decode('utf-8', errors='ignore')
                    body = body_raw.lower()
                    allowed_statuses = [int(s) for s in path_matchers.get('status', [])]
                    if status_code in allowed_statuses:
                        weight_error = 0
                        weight_payload = 0
                        error_patterns = {
                            "404 not found": 50,"access denied":50, "denied":50 ,  "not found ":50, "не найдено":50 ,"page not found": 50, "страница не найдена": 50,
                            "not found on this server": 40, "error 404": 40, "bad request": 30,
                            "requested resource": 25, "is not available": 25, "cannot find": 25,
                            "does not exist": 25, "broken link": 25, "missing page": 25,
                            "invalid resource": 20, "tomcat": 20, "exception": 15, "ошибка": 10,

                        }

                        body_temp = body
                        for pattern, weight in error_patterns.items():
                            count = body_temp.count(pattern)
                            if count > 0:
                                weight_error += count * weight
                                body_temp = body_temp.replace(pattern, "")
                        is_static = any(ext in pathl for ext in ['.log', '.txt', '.sql', '.bak', '.env', '.zip', '.tar', '.gz'])
                        if '.env' in pathl:
                            html_ind =  ["<html", "<!doctype", "<body", "<head", "href="]
                            html_score = sum(body.count(ind) for ind in html_ind)
                            if html_score > 0:
                                weight_payload = 0
                                weight_error += html_score * 40
                            else:
                                env_keys = ["db_", "app_", "secret", "password", "aws_", "token", "jwt_", "redis_"]
                                matches_count = sum(body.count(k) for k in env_keys)
                                regex_matches = len(re.findall(r'^[a-z0-9_]+=', body, re.MULTILINE))
                                weight_payload = (matches_count * 15) + (regex_matches * 35)
                        elif '.git/config' in pathl:
                            if '[core]' in body:
                                weight_payload = 200
                        elif any(ext in pathl for ext in [".zip", ".sql", ".tar", ".bak", ".gz"]):
                            html_indicators = ["<html", "<!doctype", "<body", "<head", "href="]
                            html_score = sum(body.count(ind) for ind in html_indicators)
                            if html_score == 0:
                                weight_payload = 150
                            else:
                                weight_payload = 0
                                weight_error += html_score * 40
                        elif '.log' in pathl or '.txt' in pathl:
                            log_keys = ["password", "secret", "token", "credentials", "session", "key="]
                            weight_payload = sum(body.count(k) for k in log_keys) * 50
                        is_fake_404 = False
                        if weight_payload > 0:
                            weight_error = 0
                        if not is_static and weight_error >= 40:
                            is_fake_404 = True
                        if is_static and weight_error > weight_payload:
                            is_fake_404 = True
                        if is_static and weight_payload == 0:
                            is_fake_404 = True
                        if status_code == 200 and ("swagger" in pathl or "api" in pathl or "docs" in pathl):
                            if body.strip().startswith("{") and '"error"' in body:
                                is_fake_404 = True
                            elif "swagger-ui" not in body and "openapi" not in body and "redoc" not in body:
                                if "whitelabel error page" in body or '"status":404' in body:
                                    is_fake_404 = True
                        if not is_fake_404 and status_code == 403:
                            is_fake_404 = True
                        if not is_fake_404:
                            await self.report_vuln(url, test_url, f"Утечка найдена ({status_code})", 80)
                            return {"status": "vulnerable", "url": test_url}

                except Exception as e:
                    print(f"ошибка {e}")
                return None

    async def doublechecl(self, session,test_url,base_elapsed):
       try:
          parsed = urlparse(test_url)
          params = parse_qsl(parsed.query)
          mutparams = []
          for pname,pval in params:
              decoded = self.pld.mixeddecode(pval)
              if '0:0:4' in decoded: decoded = decoded.replace("0:0:4", "0:0:9")
              elif '0:0:5'in decoded: decoded=decoded.replace("0:0:5", "0:0:9")
              else:decoded = re.sub(r'\b(4|5)\b', '9',decoded)
              encoded = self.pld.mixedencode(decoded , mode="hex")
              print(encoded)
              mutparams.append((pname,encoded))
          control_url = urlunparse(parsed._replace(query=urlencode(mutparams)))
          print(control_url)
          await asyncio.sleep(0.5)
          start =  asyncio.get_running_loop().time()
          await session.get(control_url, timeout=13)
          check_elapsed = asyncio.get_running_loop().time() - start
          print(check_elapsed)
          print(f"Базовое  {base_elapsed}")
          self.logger.log("info", f"{base_elapsed}")
          if check_elapsed >= 8.5 and check_elapsed > (base_elapsed + 2.5):
              return True
          return False
       except Exception as e:
        print(f" Ошибка даблчека :{e}")
        return False
    async def probe_fuzz(self, session:AsyncSession, originalUrl, test_url, category, matchers):
            try:
                start_time = asyncio.get_running_loop().time()
                print(f"Начальное время{start_time}")
                resp = await session.get(test_url, timeout=6)
                elapsed = asyncio.get_running_loop().time() - start_time
                print(elapsed)
                body = resp.text
                print(f"Тело запроса")
                if elapsed < 3.5:
                  self.rsd.logreq(originalUrl, elapsed)
                susp_time =  self.rsd.check_anomaly(originalUrl)
                if susp_time or elapsed >= 4.0:
                    if "sql" not in category.lower():
                        print(f"Отброшена ложная уявзимость в тайм бейсед  {category}")
                        self.logger.log("info" ,f"Отброшена ложная уязвимость в тайм бейсед")
                        return None
                    await asyncio.sleep(1.5)
                    is_real =  await self.doublechecl(session,test_url,elapsed)
                    print(is_real)
                    if is_real:
                        await self.report_vuln(originalUrl, test_url, f"Иньекция сработала (Time-Based {category})", 95)
                        return {"status": "vulnerable", "url": test_url, "vuln_type": f"time{category}"}
                    else:
                        print("Вернуласб пустота")
                        return None

                allowed_statuses = matchers.get("status", [])
                print(allowed_statuses)
                if resp.status_code in allowed_statuses or resp.status_code >= 500:
                    if resp.status_code== 200:
                        bodyl = body.lower()
                        if any( x in bodyl for x in ['404 not found', 'страница не найдена','page not found']):
                            return None
                    regexes = matchers.get('regex', [])
                    for regex in regexes:
                        if re.search(regex, body, re.IGNORECASE):
                            parsed_test = urlparse(test_url)
                            is_reflected_ech =  False
                            for pname,pval in parse_qsl(parsed_test.query):
                                if pval and pval.lower() in body.lower():
                                    if body.lower().count(regex.lower()) <= body.lower().count(pval.lower()):
                                        is_reflected_ech = True
                                        break
                            if is_reflected_ech:
                                 continue

                            await self.report_vuln(originalUrl, test_url, f"Иньекция сработала ({category})", 100)
                            return {"status": "vulnerable", "url": test_url, "vuln_type": category, "score": 100}

            except asyncio.TimeoutError:
                print(f"подозрение на тайм аут в {test_url}  перепроверяю......")
                is_real = await self.doublechecl(session,test_url,base_elapsed=6.0)
                if is_real:
                    await self.report_vuln(originalUrl, test_url, f"Иньекция сработала (Timeout {category})", 90)
                    return {"status": "vulnerable", "url": test_url, "vuln_type": f"timeout {category}", "score": 90}
                else:
                    print(f"Отброшен ложный тайм аут {test_url}")
                    return None
            except Exception as e:
                print(F"Ошибка в фаззере :{e}")
                pass
            return None

    async def report_vuln(self, base_url, found_url, vuln_type, score):
        print(f"{vuln_type} в адресе {found_url}")
        #self.signals.node_added.emit(found_url, score, 'vulnerable')
        await self.manager.add_node(found_url,label=found_url, score=score, status='vulnerable')
        await self.manager.add_edge(base_url, found_url)
