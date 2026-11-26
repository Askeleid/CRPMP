import os
import shutil

import pytest
from django.contrib.auth import get_user_model
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from workspace.models import GroupMembership, Paper, ResearchGroup

User = get_user_model()


def _configure_chromium_options(options):
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")
    return options


def _click(browser, element):
    """Scroll element synchronously into the viewport center before clicking."""
    browser.execute_script(
        "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});",
        element,
    )
    element.click()


def _has_local_chrome() -> bool:
    candidates = [
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("chrome"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    return any(path and os.path.exists(path) for path in candidates)


def _has_local_edge() -> bool:
    candidates = [
        shutil.which("msedge"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    return any(path and os.path.exists(path) for path in candidates)


@pytest.fixture
def browser():
    """Provide a headless Chromium WebDriver (Chrome or Edge) with clean teardown."""
    if _has_local_chrome() or not _has_local_edge():
        options = _configure_chromium_options(webdriver.ChromeOptions())
        driver = webdriver.Chrome(options=options)
    else:
        options = _configure_chromium_options(webdriver.EdgeOptions())
        driver = webdriver.Edge(options=options)

    try:
        yield driver
    finally:
        driver.quit()


@pytest.mark.django_db(transaction=True)
def test_e2e_auth_and_group_creation(live_server, browser):
    """Register a user via /register/ and create a research group on dashboard."""
    wait = WebDriverWait(browser, 10)
    browser.get(f"{live_server.url}/register/")

    wait.until(EC.presence_of_element_located((By.ID, "id_username"))).send_keys(
        "e2e_alice"
    )
    browser.find_element(By.ID, "id_password1").send_keys("ComplexPass123!")
    browser.find_element(By.ID, "id_password2").send_keys("ComplexPass123!")
    browser.find_element(By.CSS_SELECTOR, "main button[type='submit']").click()

    wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), "Your Research Groups"))

    group_name_input = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='name']"))
    )
    group_name_input.send_keys("E2E Vision Lab")
    browser.find_element(By.CSS_SELECTOR, "textarea[name='description']").send_keys(
        "Created via Selenium browser test"
    )
    submit_btn = browser.find_element(
        By.XPATH, "//form[.//input[@name='name']]//button[@type='submit']"
    )
    submit_btn.click()

    wait.until(EC.staleness_of(submit_btn))
    wait.until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "main"), "E2E Vision Lab")
    )


@pytest.mark.django_db(transaction=True)
def test_e2e_paper_creation_and_search(live_server, browser):
    """Log in, add a paper with tags, and filter papers by keyword in the browser."""
    user = User.objects.create_user(username="e2e_bob", password="ComplexPass123!")
    group = ResearchGroup.objects.create(name="Search Lab", created_by=user)
    GroupMembership.objects.create(
        group=group, user=user, role=GroupMembership.Role.ADMIN
    )
    Paper.objects.create(
        group=group,
        added_by=user,
        title="ResNet: Deep Residual Learning",
        authors="Kaiming He, Xiangyu Zhang",
        year=2016,
    )

    wait = WebDriverWait(browser, 10)
    browser.get(f"{live_server.url}/login/")
    wait.until(EC.presence_of_element_located((By.ID, "id_username"))).send_keys(
        "e2e_bob"
    )
    browser.find_element(By.ID, "id_password").send_keys("ComplexPass123!")
    browser.find_element(By.CSS_SELECTOR, "main button[type='submit']").click()

    wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Open Group"))).click()
    wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), "Search Lab"))

    add_paper_form = browser.find_element(
        By.XPATH, "//form[.//input[@name='action' and @value='add_paper']]"
    )
    add_paper_form.find_element(By.NAME, "title").send_keys(
        "Attention Is All You Need"
    )
    add_paper_form.find_element(By.NAME, "authors").send_keys(
        "Ashish Vaswani, Noam Shazeer"
    )
    add_paper_form.find_element(By.NAME, "year").send_keys("2017")
    add_paper_form.find_element(By.NAME, "tags").send_keys("nlp, transformers")
    _click(browser, add_paper_form.find_element(By.CSS_SELECTOR, "button[type='submit']"))

    wait.until(
        EC.text_to_be_present_in_element(
            (By.TAG_NAME, "main"), "Attention Is All You Need"
        )
    )
    assert "#transformers" in browser.page_source

    search_input = browser.find_element(By.ID, "search")
    search_input.clear()
    search_input.send_keys("Vaswani")
    _click(
        browser,
        browser.find_element(
            By.XPATH, "//form[.//input[@id='search']]//button[@type='submit']"
        ),
    )

    wait.until(lambda d: "search=Vaswani" in d.current_url)
    paper_links = [
        el.text.strip()
        for el in browser.find_elements(By.CSS_SELECTOR, "h3.card-title a")
    ]
    assert "Attention Is All You Need" in paper_links
    assert "ResNet: Deep Residual Learning" not in paper_links


@pytest.mark.django_db(transaction=True)
def test_e2e_citation_strategy_and_experiment_log(live_server, browser):
    """Switch citation format to IEEE and submit an experiment log on paper detail."""
    user = User.objects.create_user(username="e2e_carol", password="ComplexPass123!")
    group = ResearchGroup.objects.create(name="Citation Lab", created_by=user)
    GroupMembership.objects.create(
        group=group, user=user, role=GroupMembership.Role.ADMIN
    )
    paper = Paper.objects.create(
        group=group,
        added_by=user,
        title="LoRA: Low-Rank Adaptation",
        authors="Edward Hu, Yelong Shen",
        year=2021,
        doi="10.48550/arXiv.2106.09685",
    )

    wait = WebDriverWait(browser, 10)
    browser.get(f"{live_server.url}/login/")
    wait.until(EC.presence_of_element_located((By.ID, "id_username"))).send_keys(
        "e2e_carol"
    )
    browser.find_element(By.ID, "id_password").send_keys("ComplexPass123!")
    browser.find_element(By.CSS_SELECTOR, "main button[type='submit']").click()

    wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), "Your Research Groups"))
    browser.get(f"{live_server.url}/papers/{paper.id}/")

    citation_el = wait.until(EC.presence_of_element_located((By.ID, "citation-text")))
    assert "@article{hu2021," in citation_el.text

    select = Select(browser.find_element(By.NAME, "cite_format"))
    select.select_by_value("ieee")

    expected_ieee = (
        'Edward Hu, Yelong Shen, "LoRA: Low-Rank Adaptation," '
        "2021. doi: 10.48550/arXiv.2106.09685."
    )
    wait.until(
        EC.text_to_be_present_in_element((By.ID, "citation-text"), expected_ieee)
    )
    assert browser.find_element(By.ID, "citation-text").text.strip() == expected_ieee

    log_form = browser.find_element(
        By.XPATH, "//form[.//textarea[@name='hypothesis']]"
    )
    log_form.find_element(By.NAME, "title").send_keys("Rank-8 Ablation")
    log_form.find_element(By.NAME, "hypothesis").send_keys(
        "Rank 8 retains 99% downstream accuracy."
    )
    log_form.find_element(By.NAME, "parameters").send_keys("r=8, alpha=16")
    log_form.find_element(By.NAME, "result_summary").send_keys(
        "Achieved 99.1% accuracy with 65% fewer trainable parameters."
    )
    _click(browser, log_form.find_element(By.CSS_SELECTOR, "button[type='submit']"))

    wait.until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "main"), "Rank-8 Ablation")
    )
    assert "Achieved 99.1% accuracy with 65% fewer trainable parameters." in browser.page_source
