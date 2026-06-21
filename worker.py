import random
import socket
import sys
import threading
import time
import traceback
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import QThread, Signal


class SpeedTestWorker(QThread):
    progress = Signal(str, float)
    ping_result = Signal(float)
    download_result = Signal(float)
    upload_result = Signal(float)
    jitter_result = Signal(float)
    server_info = Signal(dict)
    error = Signal(str)
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        self._cancel = False
        # Tenta import speedtest-cli (modo biblioteca)
        sys.modules["__builtin__"] = __builtins__
        try:
            import speedtest as st
            self._run_via_lib(st)
        except Exception:
            self._run_http_test()

    # ── Modo 1: speedtest-cli via import ─────────────────────────────
    def _run_via_lib(self, st):
        try:
            self.progress.emit("servidor", 0)
            s = st.Speedtest()
            if self._cancel:
                return

            s.get_best_server()
            best = s.results.server
            self.progress.emit("ping", 10)

            pings = []
            total = s.results.ping
            for i in range(3):
                if self._cancel:
                    return
                try:
                    t0 = time.time()
                    base = best["url"][: best["url"].rfind("/")]
                    s._opener.open(f"{base}/latency.txt?x={int(time.time()*1000)}.{i}")
                    elapsed = (time.time() - t0) * 1000
                    pings.append(elapsed)
                except Exception:
                    pings.append(total if total else 50.0)

            ping_val = total
            jitter_val = (
                sum(abs(p - sum(pings) / len(pings)) for p in pings) / len(pings)
                if pings else 0
            )
            self.ping_result.emit(ping_val)
            self.jitter_result.emit(jitter_val)
            if self._cancel:
                return

            self.progress.emit("download", 30)
            dl_p = {"c": 0, "t": 0}
            dl_data = {"threads": {}, "total": 0, "t0": 0, "last": 0}
            dl_lock = threading.Lock()
            def dl_cb(c, t, start=False, end=False):
                tid = threading.current_thread().ident
                with dl_lock:
                    if start:
                        if dl_data["t0"] == 0:
                            dl_data["t0"] = time.time()
                        dl_data["threads"][tid] = 0
                    elif end:
                        dl_data["threads"][tid] = t
                        dl_data["total"] = sum(dl_data["threads"].values())
                        dl_p["c"] += 1
                        pct = min(30 + (dl_p["c"] / max(dl_p["t"], 1)) * 40, 70)
                        self.progress.emit("download", pct)
                        elapsed = time.time() - dl_data["t0"]
                        if elapsed > 0:
                            self.download_result.emit((dl_data["total"] * 8) / (elapsed * 1_000_000))
                    else:
                        dl_data["threads"][tid] = c
                        dl_data["total"] = sum(dl_data["threads"].values())
                        now = time.time()
                        if now - dl_data["last"] > 0.25:
                            dl_data["last"] = now
                            elapsed = now - dl_data["t0"]
                            if elapsed > 0:
                                self.download_result.emit((dl_data["total"] * 8) / (elapsed * 1_000_000))
            s.download(callback=dl_cb)
            self.download_result.emit(s.results.download / 1_000_000)
            if self._cancel:
                return

            self.progress.emit("upload", 70)
            ul_p = {"c": 0, "t": 0}
            ul_data = {"threads": {}, "total": 0, "t0": 0, "last": 0}
            ul_lock = threading.Lock()
            def ul_cb(c, t, start=False, end=False):
                tid = threading.current_thread().ident
                with ul_lock:
                    if start:
                        if ul_data["t0"] == 0:
                            ul_data["t0"] = time.time()
                        ul_data["threads"][tid] = 0
                    elif end:
                        ul_data["threads"][tid] = t
                        ul_data["total"] = sum(ul_data["threads"].values())
                        ul_p["c"] += 1
                        pct = min(70 + (ul_p["c"] / max(ul_p["t"], 1)) * 28, 98)
                        self.progress.emit("upload", pct)
                        elapsed = time.time() - ul_data["t0"]
                        if elapsed > 0:
                            self.upload_result.emit((ul_data["total"] * 8) / (elapsed * 1_000_000))
                    else:
                        ul_data["threads"][tid] = c
                        ul_data["total"] = sum(ul_data["threads"].values())
                        now = time.time()
                        if now - ul_data["last"] > 0.25:
                            ul_data["last"] = now
                            elapsed = now - ul_data["t0"]
                            if elapsed > 0:
                                self.upload_result.emit((ul_data["total"] * 8) / (elapsed * 1_000_000))
            s.upload(callback=ul_cb)
            self.upload_result.emit(s.results.upload / 1_000_000)

            self.progress.emit("concluido", 100)
            self.server_info.emit({
                "host": best.get("host", ""),
                "name": best.get("name", ""),
                "country": best.get("country", ""),
                "sponsor": best.get("sponsor", ""),
                "latency": ping_val,
                "ip": s.results.client.get("ip", ""),
            })
            self.finished.emit()

        except Exception as e:
            self.error.emit(f"Erro no teste: {e}")

    # ── Modo 2: fallback HTTP puro ───────────────────────────────────
    def _run_http_test(self):
        try:
            self.progress.emit("servidor", 5)

            # Ping / Jitter
            ping_val = 0.0
            pings = []
            urls = [
                "https://httpbin.org/get",
                "https://cloudflare.com/cdn-cgi/trace",
                "https://www.google.com",
            ]
            for i, url in enumerate(urls):
                if self._cancel:
                    return
                self.progress.emit("ping", 5 + i * 3)
                try:
                    t0 = time.time()
                    urllib.request.urlopen(url, timeout=5)
                    elapsed = (time.time() - t0) * 1000
                    pings.append(elapsed)
                except Exception:
                    pings.append(999.0)

            if pings:
                ping_val = sum(pings) / len(pings)
                mean = ping_val
                jitter_val = sum(abs(p - mean) for p in pings) / len(pings)
            else:
                jitter_val = 0.0

            self.ping_result.emit(ping_val)
            self.jitter_result.emit(jitter_val)

            if self._cancel:
                return

            # Download
            self.progress.emit("download", 15)
            dl_urls = [
                "https://proof.ovh.net/files/10Mb.dat",
                "https://ipv4.download.thinkbroadband.com/10MB.zip",
            ]
            dl_mbps = 0.0
            for dl_url in dl_urls:
                if self._cancel:
                    return
                try:
                    self.progress.emit("download", 20)
                    t0 = time.time()
                    resp = urllib.request.urlopen(dl_url, timeout=30)
                    total_bytes = 0
                    chunk = resp.read(8192)
                    while chunk:
                        if self._cancel:
                            return
                        total_bytes += len(chunk)
                        elapsed = time.time() - t0
                        if elapsed > 0:
                            current_mbps = (total_bytes * 8) / (elapsed * 1_000_000)
                            pct = min(15 + (elapsed / 15) * 55, 70)
                            self.progress.emit("download", pct)
                            dl_mbps = max(dl_mbps, current_mbps)
                            self.download_result.emit(dl_mbps)
                        chunk = resp.read(8192)
                    break
                except Exception:
                    continue

            if self._cancel:
                return
            self.download_result.emit(dl_mbps)

            # Upload (simulado com POST)
            self.progress.emit("upload", 75)
            ul_mbps = 0.0
            try:
                data = b"x" * (5 * 1024 * 1024)
                t0 = time.time()
                req = urllib.request.Request(
                    "https://httpbin.org/post",
                    data=data,
                    method="POST",
                )
                resp = urllib.request.urlopen(req, timeout=30)
                elapsed = time.time() - t0
                if elapsed > 0:
                    ul_mbps = (len(data) * 8) / (elapsed * 1_000_000)
            except Exception:
                ul_mbps = 0.0

            self.upload_result.emit(ul_mbps)
            self.progress.emit("concluido", 100)
            self.server_info.emit({
                "host": "fallback.http",
                "name": "HTTP",
                "country": "",
                "sponsor": "Speedtest (fallback)",
                "latency": ping_val,
            })
            self.finished.emit()

        except Exception as e:
            self.error.emit(f"Erro: {e}")


# ── Worker para Adblock Tester ──────────────────────────────────────

class AdblockWorker(QThread):
    progress = Signal(float)
    result = Signal(float, int, int)
    domain_status = Signal(str, bool)
    error = Signal(str)
    finished = Signal()

    BLOCKLIST_URLS = [
        "https://adaway.org/hosts.txt",
        "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=0&mimetype=plaintext",
        "https://raw.githubusercontent.com/anudeepND/blacklist/master/adservers.txt",
        "https://v.firebog.net/hosts/Easylist.txt",
        "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
        "https://v.firebog.net/hosts/Easyprivacy.txt",
        "https://raw.githubusercontent.com/bigdargon/hostsVN/master/hosts",
        "https://v.firebog.net/hosts/Prigent-Ads.txt",
        "https://hostfiles.frogeye.fr/firstparty-trackers-hosts.txt",
    ]

    HARDCODED = [
        "doubleclick.net", "ad.doubleclick.net", "googleadservices.com",
        "pagead2.googlesyndication.com", "googlesyndication.com",
        "google-analytics.com", "googletagmanager.com", "googletagservices.com",
        "adsrvr.org", "adnxs.com", "rubiconproject.com", "criteo.com",
        "criteo.net", "casalemedia.com", "openx.net", "pubmatic.com",
        "contextweb.com", "sharethrough.com", "indexww.com", "servedby.com",
        "adzerk.net", "adsafeprotected.com", "moatads.com",
        "scorecardresearch.com", "quantserve.com", "comscore.com",
        "outbrain.com", "taboola.com", "exponential.com", "tribalfusion.com",
        "bluekai.com", "exelator.com", "demdex.net",
        "advertising.com", "2o7.net", "amazon-adsystem.com", "adform.com",
        "adition.com", "adserver.com", "yieldmanager.net",
        "adap.tv", "advertising.yahoo.com", "analytics.yahoo.com",
        "ads.linkedin.com", "adsymptotic.com", "agkn.com",
        "amobee.com", "appnexus.com", "atdmt.com", "betweendigital.com",
        "bids.io", "bidswitch.net", "bluehost.com",
        "braze.com", "branch.io", "bttrack.com",
        "cdnwidget.com", "clickfuse.com", "clicktripz.com",
        "conversantmedia.com", "convertro.com", "cpmstar.com",
        "crashlytics.com", "datalogix.com", "disqusads.com",
        "dpdhl.com", "dstillery.com", "edgeadx.com",
        "effectivemeasure.net", "eplanning.net", "evidon.com",
        "fifty-six.com", "flashtalking.com", "flurry.com",
        "foresee.com", "fout.jp", "freewheel.tv",
        "gitads.com", "goadservices.com", "grabify.link",
        "gwallet.com", "hey.xyz", "hotjar.com",
        "hubspot.com", "ignitad.com", "improvedigital.com",
        "infolinks.com", "innovid.com", "integralads.com",
        "ipredictive.com", "ipromote.com", "iteratehq.com",
        "justpremium.com", "jwplayer.com", "kargo.com",
        "kongregate.com", "kontagent.com", "leadboltads.net",
        "livefyre.com", "liveintent.com", "liveramp.com",
        "lotame.com", "madisonlogic.com", "mailstat.us",
        "marketo.com", "mathtag.com", "maxmind.com",
        "media.net", "media6degrees.com", "mediaplex.com",
        "microsoftadvertising.com", "millennialmedia.com", "mixpanel.com",
        "mookie1.com", "mparticle.com", "mty.ai",
        "myads.com", "nanigans.com", "nativeads.com",
        "neustar.biz", "newrelic.com", "nielsen.com",
        "nginx.com", "notice.news", "nr-data.net",
        "nugg.ad", "nuisance.digital", "oadz.com",
        "oath.com", "onclickads.net", "onetag.com",
        "opentracker.net", "optimizely.com", "orbitz.com",
        "outbrain.com", "owneriq.com", "parsely.com",
        "pepperjam.com", "permutive.com", "pinterest.com",
        "pixfuture.com", "plausible.io", "pntra.com",
        "po.st", "popads.net", "postrelease.com",
        "powerlinks.com", "pro-market.net", "proofpoint.com",
        "propellerads.com", "prosperent.com", "pusher.com",
        "quantcount.com", "quantummetric.com", "quora.com",
        "quotescollective.com", "revcontent.com", "revjet.com",
        "revsci.net", "rhythmone.com", "richrelevance.com",
        "rmxads.com", "roi.me", "rsz.sk",
        "sail-horizon.com", "sail-thru.com", "salesforce.com",
        "scarabresearch.com", "scorecardresearch.com", "script.io",
        "searchignite.com", "segment.io", "segments.com",
        "sekindo.com", "semasio.com", "serving-sys.com",
        "sfmc.jp", "shareaholic.com", "simpli.fi",
        "sitescout.com", "smartadserver.com", "smartclip.net",
        "snapchat.com", "snowplowanalytics.com", "soasta.com",
        "socsi.com", "sonobi.com", "specificmedia.net",
        "sptag.com", "stackadapt.com", "startapp.com",
        "statcounter.com", "staticstuff.net", "steelhouse.com",
        "stickyadstv.com", "storify.com", "stripe.com",
        "sublime.xyz", "sumo.com", "supersonicads.com",
        "survicate.com", "taboola.com", "tail.digital",
        "tapad.com", "tapjoy.com", "targeting.com",
        "tawk.to", "teads.tv", "tealium.com",
        "telaria.com", "telenet.io", "theadex.com",
        "thetradedesk.com", "thismeans.com", "tidaltv.com",
        "tiktok.com", "tinypass.com", "tint.com",
        "trackjs.com", "tracking101.com", "trackingsoft.com",
        "tradeadexchange.com", "trafficfactory.com", "trafficjunky.com",
        "trafficstars.com", "treasuredata.com", "trendmd.com",
        "triplelift.com", "trueffect.com", "trustarc.com",
        "tube8.com", "turn.com", "tweetdeck.com",
        "twitch.com", "twitter.com", "typesquare.com",
        "uberads.com", "ugdturner.com", "undertone.com",
        "unica.com", "unified.com", "unit5.org",
        "unruly.co", "uplynk.com", "usemessages.com",
        "uservoice.com", "v12data.com", "valuedopinions.com",
        "velti.com", "venturebeat.com", "vericlick.com",
        "verticalresponse.com", "vertize.com", "vibrantmedia.com",
        "videoamp.com", "videologygroup.com", "viglink.com",
        "visiblemeasures.com", "visibli.com", "visualdna.com",
        "vizu.com", "vkontakte.com", "voicefive.com",
        "voluum.com", "voxus.com", "vungle.com",
        "w55c.net", "washingtonpost.com", "wdfl.co",
        "webads.com", "webchat.com", "webmarketing123.com",
        "webtrends.com", "webtrekk.com", "weibo.com",
        "wexperience.com", "whatcounts.com", "whisper.net",
        "widgetserver.com", "wishabi.com", "woopra.com",
        "wordstream.com", "wunderloop.net", "xad.com",
        "xaxis.com", "xbox.com", "xiti.com",
        "xtify.com", "yabidos.com", "yahoo.com",
        "yandex.com", "yb.utils", "ybrantdigital.com",
        "yceml.net", "ydn.com", "yieldbot.com",
        "yieldmo.com", "yieldoptimizer.com", "yieldtraffic.com",
        "yimg.com", "yldmgrimg.net", "yoc.com",
        "yoggrt.com", "youronlinechoices.com", "yp.com",
        "yumenetworks.com", "zanox.com", "zarget.com",
        "zendesk.com", "zergnet.com", "zeusclicks.com",
        "ziffdavis.com", "zmedia.com", "zoosk.com",
        "adsrvr.org", "advertising.com", "zypmedia.com",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            self.progress.emit(2)
            domains = self._fetch_domains()
            if self._cancel:
                return
            if domains:
                self._test_domains(domains)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def _fetch_domains(self):
        seen = set()
        for url in self.BLOCKLIST_URLS:
            if self._cancel:
                return list(seen)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                resp = urllib.request.urlopen(req, timeout=15)
                text = resp.read().decode("utf-8", errors="replace")
                for line in text.splitlines():
                    raw = line.strip()
                    if not raw or raw.startswith("#") or raw.startswith("!"):
                        continue
                    domain = None
                    if raw.startswith("0.0.0.0 ") or raw.startswith("127.0.0.1 "):
                        parts = raw.split()
                        if len(parts) >= 2:
                            domain = parts[1].strip().lower()
                    elif " " in raw:
                        parts = raw.split()
                        if len(parts) == 2 and parts[0].replace(".", "").isdigit():
                            domain = parts[1].strip().lower()
                    elif raw.startswith("||") and raw.endswith("^"):
                        domain = raw[2:-1].strip().lower()
                    elif raw.startswith("||") and "|" not in raw[3:]:
                        domain = raw[2:].strip().lower()
                    elif "." in raw and not raw.startswith("[") and "=" not in raw:
                        domain = raw.lower()
                    if domain and "." in domain and not domain.startswith(".") and not domain.endswith("."):
                        seen.add(domain)
                        if len(seen) >= 500:
                            return list(seen)
            except Exception:
                continue
        if not seen:
            return self.HARDCODED[:]
        return list(seen)

    def _check_one(self, domain):
        try:
            sock = socket.create_connection((domain, 443), timeout=1.5)
            sock.close()
            return False
        except Exception:
            return True

    def _test_domains(self, domains):
        total = min(len(domains), 200)
        domains = domains[:200]
        blocked = 0
        results = []
        with ThreadPoolExecutor(max_workers=30) as ex:
            fut_map = {ex.submit(self._check_one, d): d for d in domains}
            for future in as_completed(fut_map):
                if self._cancel:
                    for f in fut_map:
                        f.cancel()
                    break
                results.append(future.result())
                tested = len(results)
                blk = sum(1 for r in results if r)
                self.progress.emit((blk / tested) * 100)
        if self._cancel and results:
            blk = sum(1 for r in results if r)
            self.result.emit((blk / len(results)) * 100, len(results), blk)
            self.finished.emit()
            return
        blocked = sum(1 for r in results if r)
        tested = len(results)
        result_pct = (blocked / tested * 100) if tested > 0 else 0
        self.result.emit(result_pct, tested, blocked)
        self.finished.emit()
