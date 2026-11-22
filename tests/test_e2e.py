import subprocess
import sys
import time

import pytest
from playwright.sync_api import sync_playwright

pytestmark = [pytest.mark.e2e]


@pytest.fixture(scope="module")
def server():
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8111"],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(8)
    yield proc
    proc.terminate()
    proc.wait(timeout=10)


def test_e2e_search_and_results(server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto("http://localhost:8111")
        assert "Goofish" in page.title()

        page.fill("#searchInput", "手机壳")
        page.press("#searchInput", "Enter")

        page.wait_for_timeout(15000)

        status = page.text_content("#statusBar")
        assert status is not None

        cards = page.query_selector_all(".product-card")

        browser.close()


def test_e2e_no_console_errors(server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))

        page.goto("http://localhost:8111")
        page.wait_for_timeout(2000)

        assert len(errors) == 0, f"Console errors: {errors}"
        browser.close()
