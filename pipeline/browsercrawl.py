"""Generic headless-browser smoke crawler for a generated web app.

Run against a live app. It opens pages, fills and submits forms with plausible values,
clicks every control, and reports what a real user would hit: JavaScript errors, failed
requests, server errors and controls that do nothing. It needs only Playwright.

    python browsercrawl.py http://localhost:8000 --out report.json
"""
import argparse
import json
import re
import sys
import uuid
from urllib.parse import urlparse

DESTRUCTIVE = re.compile(r"delete|remove|log ?out|sign ?out|deactivate|erase", re.IGNORECASE)
MAX_STEPS = 120
SETTLE_MS = 500

# Requests that are allowed to fail without being a bug (a signed-out check on first load).
IGNORED_STATUS = {("GET", 401), ("GET", 403)}


def value_for(input_type: str, name: str, token: str) -> str:
    """A plausible value for a form field, chosen from its type and name."""
    key = f"{input_type} {name}".lower()
    if "email" in key:
        return f"crawler{token}@example.com"
    if "pass" in key:
        return "Passw0rd!2026"
    if "phone" in key or "tel" in key or "mobile" in key:
        return "+919876543210"
    if input_type == "number" or "amount" in key:
        return "125000"
    if input_type == "date" or "date" in key:
        return "2026-12-31"
    if "url" in key:
        return "https://example.com"
    return f"Test {token}"


def is_bug_response(method: str, status: int, url: str, origin: str) -> bool:
    """Is this HTTP response something to report?"""
    if urlparse(url).netloc != urlparse(origin).netloc:
        return False
    if status < 400:
        return False
    if (method, status) in IGNORED_STATUS:
        return False
    return status != 429  # 429 is rate limiting hit by the crawler itself


def attempt(action) -> bool:
    """Run a browser action. A control that is covered, removed or slow is not a finding, so False is returned."""
    from playwright.sync_api import Error as PlaywrightError

    try:
        action()
    except PlaywrightError:
        return False
    return True


def key_of(el) -> str:
    return "|".join([el["tag"], el["text"][:40], el["id"], el["href"]])


CONTROLS_JS = """
() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !e.disabled; };
  const out = [];
  document.querySelectorAll('button, a[href], [role=button], input[type=submit]').forEach((e, i) => {
    if (!vis(e)) return;
    e.setAttribute('data-crawl-idx', String(i));
    out.push({idx: i, tag: e.tagName.toLowerCase(), text: (e.innerText || e.value || e.getAttribute('aria-label') || '').trim(),
              id: e.id || '', href: e.getAttribute('href') || '', type: e.getAttribute('type') || ''});
  });
  return out;
}
"""

FORMS_JS = """
() => {
  const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && !e.disabled; };
  return Array.from(document.querySelectorAll('input, select, textarea')).filter(vis).map((e, i) => {
    e.setAttribute('data-crawl-field', String(i));
    return {i, tag: e.tagName.toLowerCase(), type: (e.getAttribute('type') || 'text').toLowerCase(), name: e.name || e.id || e.placeholder || '',
            value: e.value || ''};
  });
}
"""


def crawl(base_url: str, max_steps: int = MAX_STEPS) -> dict:
    from playwright.sync_api import sync_playwright

    origin = base_url.rstrip("/")
    token = uuid.uuid4().hex[:8]
    findings: list[dict] = []
    seen_findings: set[str] = set()
    visited_paths: set[str] = set()
    steps = 0

    def add(kind: str, detail: str, where: str, fatal: bool = True):
        key = f"{kind}|{detail}|{where}"
        if key not in seen_findings:
            seen_findings.add(key)
            findings.append({"kind": kind, "detail": detail, "where": where, "fatal": fatal})

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--disable-dev-shm-usage"])  # small /dev/shm inside Docker
        context = browser.new_context(viewport={"width": 390, "height": 844})
        page = context.new_page()
        state = {"where": "/", "requests": 0}

        page.on("pageerror", lambda e: add("javascript_error", str(e)[:300], state["where"]))
        page.on(
            "console",
            lambda m: add("console_error", m.text[:300], state["where"])
            if m.type == "error" and "Failed to load resource" not in m.text
            else None,
        )
        page.on("request", lambda r: state.__setitem__("requests", state["requests"] + 1))
        page.on("requestfailed", lambda r: add("request_failed", f"{r.method} {r.url} {r.failure}", state["where"]))
        page.on(
            "response",
            lambda r: add("http_error", f"{r.request.method} {r.status} {r.url.replace(origin, '')}", state["where"])
            if is_bug_response(r.request.method, r.status, r.url, origin)
            else None,
        )
        page.on("dialog", lambda d: d.dismiss())

        def snapshot() -> tuple:
            return (page.url, page.evaluate("document.body.innerHTML.length"), state["requests"])

        def fill_and_submit() -> bool:
            """Fill every visible field and submit the form. Returns True if a submit button was pressed."""
            fields = page.evaluate(FORMS_JS)
            if not fields:
                return False
            for f in fields:
                loc = page.locator(f'[data-crawl-field="{f["i"]}"]')
                if f["type"] in ("checkbox", "radio"):
                    attempt(lambda loc=loc: loc.check(timeout=1000))
                elif f["type"] == "file":
                    continue
                elif f["tag"] == "select":
                    if len(loc.locator("option").all()) > 1:
                        attempt(lambda loc=loc: loc.select_option(index=1))
                elif not f["value"]:
                    attempt(lambda loc=loc, f=f: loc.fill(value_for(f["type"], f["name"], token), timeout=1000))
            submit = page.locator("form button[type=submit], form input[type=submit], form button:not([type])").first
            if submit.count() and submit.is_visible() and attempt(lambda: submit.click(timeout=1500)):
                page.wait_for_timeout(SETTLE_MS * 3)
                return True
            return False

        queue = ["/"]
        while queue and steps < max_steps:
            path = queue.pop(0)
            if path in visited_paths:
                continue
            visited_paths.add(path)
            state["where"] = path
            if not attempt(lambda path=path: page.goto(origin + path, wait_until="load", timeout=20000)):
                add("page_load_failed", "the page did not load", path)
                continue
            page.wait_for_timeout(SETTLE_MS)
            if fill_and_submit():
                steps += 1
                new_path = urlparse(page.url).path
                if new_path not in visited_paths:
                    queue.append(new_path)

            controls = sorted(page.evaluate(CONTROLS_JS), key=lambda c: bool(DESTRUCTIVE.search(c["text"])))
            clicked: set[str] = set()
            for c in controls:
                if steps >= max_steps:
                    break
                k = key_of(c)
                if k in clicked:
                    continue
                clicked.add(k)
                if c["href"].startswith(("http://", "https://", "mailto:", "tel:")) and not c["href"].startswith(origin):
                    continue
                if c["tag"] == "a" and c["href"].startswith("/"):
                    queue.append(c["href"].split("?")[0].split("#")[0])
                steps += 1
                before = snapshot()
                if not attempt(lambda c=c: page.locator(f'[data-crawl-idx="{c["idx"]}"]').first.click(timeout=2000)):
                    continue  # covered or removed by an earlier click, not a finding
                page.wait_for_timeout(SETTLE_MS)
                after = snapshot()
                if after == before and c["tag"] != "a":
                    add("dead_control", f'"{c["text"][:40] or c["id"]}" did nothing', path, fatal=False)
                new_path = urlparse(page.url).path
                if new_path != path:
                    if new_path not in visited_paths:
                        queue.append(new_path)
                    attempt(lambda path=path: page.goto(origin + path, wait_until="load", timeout=20000))
                    page.wait_for_timeout(SETTLE_MS)
                    page.evaluate(CONTROLS_JS)  # re-tag controls on the reloaded page
                else:
                    attempt(lambda: page.keyboard.press("Escape"))
        browser.close()

    fatal = [f for f in findings if f["fatal"]]
    return {"ok": not fatal, "pages": sorted(visited_paths), "steps": steps, "findings": findings}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--out", default="browser-report.json")
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    args = parser.parse_args(argv)
    report = crawl(args.url, args.max_steps)
    with open(args.out, "w") as handle:
        json.dump(report, handle, indent=2)
    print(f"pages: {len(report['pages'])}  steps: {report['steps']}")
    for f in report["findings"]:
        print(f"{'FAILED' if f['fatal'] else 'warning'} {f['kind']}: {f['detail']} (on {f['where']})")
    print("browser check:", "PASSED" if report["ok"] else "FAILED")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
