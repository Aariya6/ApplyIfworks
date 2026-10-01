"""v4.3.0 release validation harness.

Local checks are safe by default. Live source/ATS checks are opt-in and never
submit an application. Live source discovery writes source-health metrics to the
local SQLite database; run it on an Internet-connected machine.
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def chromium():
    return os.getenv("RJP_CHROMIUM_EXECUTABLE") or shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")


def local_checks():
    print("Chromium:", chromium() or "NOT FOUND")
    if not chromium() and not Path.home().joinpath('.cache/ms-playwright').exists():
        return False
    r=subprocess.run([sys.executable,"-m","pytest","-q"],cwd=ROOT)
    return r.returncode==0


def live_sources():
    from app.services.discovery import discover
    total, errors=discover()
    from app.db import source_health
    rows=source_health()
    print(json.dumps({"jobs_discovered":total,"errors":errors,"sources":rows},indent=2,ensure_ascii=False))
    return not errors


def live_ats(urls):
    from playwright.sync_api import sync_playwright
    if not all(urls.values()):
        print("Provide --greenhouse-url, --lever-url and --ashby-url for live ATS validation.")
        return False
    exe=chromium()
    if not exe: return False
    results={}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=exe,args=['--no-sandbox'])
        for name,url in urls.items():
            page=browser.new_page()
            try:
                response=page.goto(url,wait_until="domcontentloaded",timeout=60000)
                body=(page.locator('body').inner_text(timeout=15000) or '').lower()
                fields=page.locator('input,textarea,select').count()
                blocked=any(x in body for x in ['captcha','recaptcha','hcaptcha','verify you are human','multi-factor','two-factor','security challenge'])
                results[name]={"http_status":response.status if response else None,"url":page.url,"form_fields":fields,"human_gate_detected":blocked,"submission_performed":False}
            except Exception as e:
                results[name]={"error":str(e),"submission_performed":False}
            finally: page.close()
        browser.close()
    print(json.dumps(results,indent=2))
    return all("error" not in x and x["form_fields"]>0 for x in results.values())


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--live-sources',action='store_true')
    ap.add_argument('--live-ats',action='store_true')
    ap.add_argument('--greenhouse-url')
    ap.add_argument('--lever-url')
    ap.add_argument('--ashby-url')
    a=ap.parse_args()
    ok=local_checks()
    if a.live_sources: ok=live_sources() and ok
    if a.live_ats: ok=live_ats({'greenhouse':a.greenhouse_url,'lever':a.lever_url,'ashby':a.ashby_url}) and ok
    raise SystemExit(0 if ok else 1)

if __name__=='__main__': main()
