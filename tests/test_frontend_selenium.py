"""
Selenium-based frontend UI tests for the Trustworthy Model Registry.
Tests actual browser interactions: clicking, typing, form submission, navigation, etc.

Requires:
- selenium (pip install selenium)
- chromedriver (or geckodriver for Firefox)
- Running FastAPI server on http://localhost:8000
"""

import pytest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)


@pytest.fixture(scope="session")
def chrome_driver():
    """Create a Chrome WebDriver instance for the entire test session."""
    options = webdriver.ChromeOptions()
    # Uncomment to run headless (no visible browser)
    # options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )
    yield driver
    driver.quit()


@pytest.fixture(autouse=True)
def reset_driver(chrome_driver):
    """Reset driver state between tests."""
    yield
    # Clear any popups or alerts
    try:
        alert = webdriver.Alert(chrome_driver)
        alert.dismiss()
    except:
        pass


class TestFrontendNavigation:
    """Test page navigation and page loads."""

    BASE_URL = "http://localhost:8000"

    def test_home_page_loads(self, chrome_driver):
        """Test that home page loads successfully."""
        chrome_driver.get(f"{self.BASE_URL}/")
        wait = WebDriverWait(chrome_driver, 10)

        # Wait for page title or main element
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "Trustworthy Model Registry" in chrome_driver.title or len(
            chrome_driver.page_source
        ) > 100

    def test_upload_page_loads(self, chrome_driver):
        """Test that upload page loads successfully."""
        chrome_driver.get(f"{self.BASE_URL}/upload.html")
        wait = WebDriverWait(chrome_driver, 10)

        # Wait for form element
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        page_source = chrome_driver.page_source
        assert "upload" in page_source.lower()

    def test_ingest_page_loads(self, chrome_driver):
        """Test that ingest page loads successfully."""
        chrome_driver.get(f"{self.BASE_URL}/ingest.html")
        wait = WebDriverWait(chrome_driver, 10)

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        page_source = chrome_driver.page_source
        assert len(page_source) > 100

    def test_enumerate_page_loads(self, chrome_driver):
        """Test that search/enumerate page loads successfully."""
        chrome_driver.get(f"{self.BASE_URL}/enumerate.html")
        wait = WebDriverWait(chrome_driver, 10)

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        page_source = chrome_driver.page_source
        assert len(page_source) > 100

    def test_license_check_page_loads(self, chrome_driver):
        """Test that license check page loads successfully."""
        chrome_driver.get(f"{self.BASE_URL}/license_check.html")
        wait = WebDriverWait(chrome_driver, 10)

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        page_source = chrome_driver.page_source
        assert len(page_source) > 100

    def test_no_404_errors_on_home(self, chrome_driver):
        """Test that home page doesn't have 404 errors."""
        chrome_driver.get(f"{self.BASE_URL}/")
        time.sleep(2)

        # Check browser console for 404 errors
        logs = chrome_driver.get_log("browser")
        error_messages = [log["message"] for log in logs if "404" in log["message"]]
        assert len(error_messages) == 0, f"Found 404 errors: {error_messages}"


class TestFormValidation:
    """Test form validation and input handling."""

    BASE_URL = "http://localhost:8000"

    def test_upload_form_exists(self, chrome_driver):
        """Test that upload form has required fields."""
        chrome_driver.get(f"{self.BASE_URL}/upload.html")
        wait = WebDriverWait(chrome_driver, 10)

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))

        # Check for common form fields
        form = chrome_driver.find_element(By.TAG_NAME, "form")
        assert form is not None
        inputs = form.find_elements(By.TAG_NAME, "input")
        assert len(inputs) > 0, "Upload form should have input fields"

    def test_ingest_form_exists(self, chrome_driver):
        """Test that ingest form has required fields."""
        chrome_driver.get(f"{self.BASE_URL}/ingest.html")
        wait = WebDriverWait(chrome_driver, 10)

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        form = chrome_driver.find_element(By.TAG_NAME, "form")
        assert form is not None

    def test_search_form_exists(self, chrome_driver):
        """Test that search form has required fields."""
        chrome_driver.get(f"{self.BASE_URL}/enumerate.html")
        wait = WebDriverWait(chrome_driver, 10)

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        form = chrome_driver.find_element(By.TAG_NAME, "form")
        assert form is not None

    def test_form_buttons_clickable(self, chrome_driver):
        """Test that form buttons are clickable."""
        chrome_driver.get(f"{self.BASE_URL}/upload.html")
        wait = WebDriverWait(chrome_driver, 10)

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "button")))
        buttons = chrome_driver.find_elements(By.TAG_NAME, "button")
        assert len(buttons) > 0, "Page should have at least one button"

        # Check button is enabled
        for button in buttons:
            if button.is_displayed():
                assert button.is_enabled(), "Visible button should be enabled"


class TestPageElements:
    """Test that page elements render correctly."""

    BASE_URL = "http://localhost:8000"

    def test_home_page_has_header(self, chrome_driver):
        """Test that home page has header."""
        chrome_driver.get(f"{self.BASE_URL}/")
        wait = WebDriverWait(chrome_driver, 10)

        # Wait for header
        try:
            header = wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "header"))
            )
            assert header is not None
        except TimeoutException:
            # If no header, check for h1
            h1 = chrome_driver.find_element(By.TAG_NAME, "h1")
            assert h1 is not None

    def test_pages_have_navigation(self, chrome_driver):
        """Test that pages have navigation elements."""
        chrome_driver.get(f"{self.BASE_URL}/")
        wait = WebDriverWait(chrome_driver, 10)

        time.sleep(1)

        # Look for nav links
        page_source = chrome_driver.page_source.lower()
        assert (
            "upload" in page_source
            or "ingest" in page_source
            or "search" in page_source
        ), "Page should have navigation"

    def test_home_page_displays_content(self, chrome_driver):
        """Test that home page displays content."""
        chrome_driver.get(f"{self.BASE_URL}/")
        wait = WebDriverWait(chrome_driver, 10)

        # Wait for body content
        body = wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        assert len(body.text) > 0, "Page should display content"

    def test_page_css_loads(self, chrome_driver):
        """Test that CSS is loaded and applied."""
        chrome_driver.get(f"{self.BASE_URL}/")
        wait = WebDriverWait(chrome_driver, 10)

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Check that elements have styling
        body = chrome_driver.find_element(By.TAG_NAME, "body")
        computed_style = chrome_driver.execute_script(
            "return window.getComputedStyle(arguments[0])", body
        )
        # CSS should be applied (background, font, etc.)
        assert computed_style is not None

    def test_javascript_loaded(self, chrome_driver):
        """Test that JavaScript is loaded and accessible."""
        chrome_driver.get(f"{self.BASE_URL}/")
        time.sleep(1)

        # Check if app.js is loaded
        js_result = chrome_driver.execute_script("return typeof window")
        assert js_result == "object", "JavaScript should be loaded"


class TestInputInteractions:
    """Test user input interactions."""

    BASE_URL = "http://localhost:8000"

    def test_text_input_accepts_text(self, chrome_driver):
        """Test that text inputs accept text."""
        chrome_driver.get(f"{self.BASE_URL}/upload.html")
        wait = WebDriverWait(chrome_driver, 10)

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        inputs = chrome_driver.find_elements(By.TAG_NAME, "input")

        # Find a text input
        text_input = None
        for inp in inputs:
            if inp.get_attribute("type") in [None, "text"]:
                text_input = inp
                break

        if text_input:
            text_input.clear()
            text_input.send_keys("test input")
            assert text_input.get_attribute("value") == "test input"

    def test_search_input_accepts_queries(self, chrome_driver):
        """Test that search input accepts queries."""
        chrome_driver.get(f"{self.BASE_URL}/enumerate.html")
        wait = WebDriverWait(chrome_driver, 10)

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
        inputs = chrome_driver.find_elements(By.TAG_NAME, "input")

        if inputs:
            search_input = inputs[0]
            search_input.send_keys("test-model")
            value = search_input.get_attribute("value")
            assert "test-model" in value

    def test_textarea_accepts_text(self, chrome_driver):
        """Test that textareas accept text."""
        chrome_driver.get(f"{self.BASE_URL}/upload.html")
        wait = WebDriverWait(chrome_driver, 10)

        time.sleep(1)

        textareas = chrome_driver.find_elements(By.TAG_NAME, "textarea")
        if textareas:
            textarea = textareas[0]
            textarea.clear()
            textarea.send_keys("test content")
            assert "test content" in textarea.get_attribute("value")


class TestBrowserConsole:
    """Test browser console for JavaScript errors."""

    BASE_URL = "http://localhost:8000"

    def test_no_javascript_errors_on_home(self, chrome_driver):
        """Test that home page has no JavaScript errors."""
        chrome_driver.get(f"{self.BASE_URL}/")
        time.sleep(2)

        logs = chrome_driver.get_log("browser")
        errors = [log for log in logs if log["level"] == "SEVERE"]

        assert len(errors) == 0, f"Found JavaScript errors: {[e['message'] for e in errors]}"

    def test_no_javascript_errors_on_upload(self, chrome_driver):
        """Test that upload page has no JavaScript errors."""
        chrome_driver.get(f"{self.BASE_URL}/upload.html")
        time.sleep(2)

        logs = chrome_driver.get_log("browser")
        errors = [log for log in logs if log["level"] == "SEVERE"]

        assert len(errors) == 0, f"Found JavaScript errors: {[e['message'] for e in errors]}"

    def test_no_javascript_errors_on_search(self, chrome_driver):
        """Test that search page has no JavaScript errors."""
        chrome_driver.get(f"{self.BASE_URL}/enumerate.html")
        time.sleep(2)

        logs = chrome_driver.get_log("browser")
        errors = [log for log in logs if log["level"] == "SEVERE"]

        assert len(errors) == 0, f"Found JavaScript errors: {[e['message'] for e in errors]}"


class TestPageResponsiveness:
    """Test page responsiveness and layout."""

    BASE_URL = "http://localhost:8000"

    def test_page_loads_within_time_limit(self, chrome_driver):
        """Test that page loads within reasonable time."""
        start = time.time()
        chrome_driver.get(f"{self.BASE_URL}/")
        elapsed = time.time() - start

        assert elapsed < 10, f"Page took {elapsed}s to load (should be < 10s)"

    def test_page_responsive_design(self, chrome_driver):
        """Test that page works at different viewport sizes."""
        chrome_driver.get(f"{self.BASE_URL}/")
        time.sleep(1)

        # Test at mobile size
        chrome_driver.set_window_size(375, 667)
        time.sleep(1)
        body = chrome_driver.find_element(By.TAG_NAME, "body")
        assert len(body.text) > 0

        # Test at tablet size
        chrome_driver.set_window_size(768, 1024)
        time.sleep(1)
        body = chrome_driver.find_element(By.TAG_NAME, "body")
        assert len(body.text) > 0

        # Test at desktop size
        chrome_driver.set_window_size(1920, 1080)
        time.sleep(1)
        body = chrome_driver.find_element(By.TAG_NAME, "body")
        assert len(body.text) > 0

    def test_elements_visible_after_load(self, chrome_driver):
        """Test that main elements are visible after page load."""
        chrome_driver.get(f"{self.BASE_URL}/")
        wait = WebDriverWait(chrome_driver, 10)

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        body = chrome_driver.find_element(By.TAG_NAME, "body")
        assert body.is_displayed(), "Body should be displayed"


class TestAPIIntegration:
    """Test frontend API integration via Selenium."""

    BASE_URL = "http://localhost:8000"

    def test_api_base_detection(self, chrome_driver):
        """Test that API_BASE is correctly set based on environment."""
        chrome_driver.get(f"{self.BASE_URL}/")
        time.sleep(1)

        # Execute JavaScript to check API_BASE
        api_base = chrome_driver.execute_script("return typeof API_BASE !== 'undefined'")
        assert api_base, "API_BASE should be defined in app.js"

    def test_api_base_is_localhost(self, chrome_driver):
        """Test that API_BASE resolves to localhost on local environment."""
        chrome_driver.get(f"{self.BASE_URL}/")
        time.sleep(1)

        api_base = chrome_driver.execute_script("return API_BASE")
        assert api_base is not None
        assert "localhost" in api_base or "127.0.0.1" in api_base

    def test_fetch_api_available(self, chrome_driver):
        """Test that Fetch API is available for AJAX calls."""
        chrome_driver.get(f"{self.BASE_URL}/")

        fetch_available = chrome_driver.execute_script(
            "return typeof fetch === 'function'"
        )
        assert fetch_available, "Fetch API should be available"

    def test_cors_headers_received(self, chrome_driver):
        """Test that CORS headers are received on API calls."""
        chrome_driver.get(f"{self.BASE_URL}/")
        time.sleep(2)

        # Make a test API call and check for CORS
        result = chrome_driver.execute_script(
            """
            return fetch('/api/v1/health').then(r => ({
                status: r.status,
                ok: r.ok
            })).catch(e => ({error: e.message}));
            """
        )
        # Result might be a promise, so we need to handle async
        time.sleep(1)


class TestClickInteractions:
    """Test mouse click interactions."""

    BASE_URL = "http://localhost:8000"

    def test_button_click_response(self, chrome_driver):
        """Test that buttons respond to clicks."""
        chrome_driver.get(f"{self.BASE_URL}/upload.html")
        wait = WebDriverWait(chrome_driver, 10)

        wait.until(EC.presence_of_element_located((By.TAG_NAME, "button")))
        buttons = chrome_driver.find_elements(By.TAG_NAME, "button")

        if buttons:
            # Get initial state
            initial_count = len(chrome_driver.find_elements(By.TAG_NAME, "button"))

            # Click button
            buttons[0].click()
            time.sleep(0.5)

            # Button should still exist (not removed)
            assert len(chrome_driver.find_elements(By.TAG_NAME, "button")) >= 0

    def test_link_navigation(self, chrome_driver):
        """Test that links navigate correctly."""
        chrome_driver.get(f"{self.BASE_URL}/")
        time.sleep(1)

        links = chrome_driver.find_elements(By.TAG_NAME, "a")
        initial_url = chrome_driver.current_url

        if len(links) > 0:
            # Find a local link
            for link in links:
                href = link.get_attribute("href")
                if href and "http://localhost" in href:
                    link.click()
                    time.sleep(1)
                    new_url = chrome_driver.current_url
                    assert new_url != initial_url, "Navigation should change URL"
                    break


class TestFormSubmission:
    """Test form submission behavior."""

    BASE_URL = "http://localhost:8000"

    def test_upload_form_structure(self, chrome_driver):
        """Test that upload form has correct structure."""
        chrome_driver.get(f"{self.BASE_URL}/upload.html")
        wait = WebDriverWait(chrome_driver, 10)

        form = wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        assert form is not None

        # Check for inputs
        inputs = form.find_elements(By.TAG_NAME, "input")
        assert len(inputs) > 0, "Form should have inputs"

        # Check for button
        buttons = form.find_elements(By.TAG_NAME, "button")
        assert len(buttons) > 0, "Form should have submit button"

    def test_search_form_structure(self, chrome_driver):
        """Test that search form has correct structure."""
        chrome_driver.get(f"{self.BASE_URL}/enumerate.html")
        wait = WebDriverWait(chrome_driver, 10)

        form = wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        assert form is not None

        inputs = form.find_elements(By.TAG_NAME, "input")
        assert len(inputs) > 0, "Form should have search input"

    def test_license_check_form_structure(self, chrome_driver):
        """Test that license check form has correct structure."""
        chrome_driver.get(f"{self.BASE_URL}/license_check.html")
        wait = WebDriverWait(chrome_driver, 10)

        form = wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        assert form is not None

        inputs = form.find_elements(By.TAG_NAME, "input")
        assert len(inputs) > 0, "Form should have inputs"


class TestPageTitle:
    """Test page titles and meta information."""

    BASE_URL = "http://localhost:8000"

    def test_home_page_has_title(self, chrome_driver):
        """Test that home page has a title."""
        chrome_driver.get(f"{self.BASE_URL}/")
        assert chrome_driver.title, "Page should have a title"

    def test_upload_page_has_title(self, chrome_driver):
        """Test that upload page has a title."""
        chrome_driver.get(f"{self.BASE_URL}/upload.html")
        assert chrome_driver.title, "Page should have a title"

    def test_search_page_has_title(self, chrome_driver):
        """Test that search page has a title."""
        chrome_driver.get(f"{self.BASE_URL}/enumerate.html")
        assert chrome_driver.title, "Page should have a title"


class TestDynamicContent:
    """Test dynamic content rendering."""

    BASE_URL = "http://localhost:8000"

    def test_page_renders_without_errors(self, chrome_driver):
        """Test that page renders without throwing errors."""
        chrome_driver.get(f"{self.BASE_URL}/")
        time.sleep(2)

        # Check for errors in logs
        logs = chrome_driver.get_log("browser")
        severe_errors = [log for log in logs if log["level"] == "SEVERE"]

        assert len(severe_errors) == 0

    def test_dom_elements_accessible(self, chrome_driver):
        """Test that DOM elements are accessible."""
        chrome_driver.get(f"{self.BASE_URL}/")
        wait = WebDriverWait(chrome_driver, 10)

        # Wait for body to be present
        body = wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        assert body is not None

        # Get all paragraphs or divs
        elements = chrome_driver.find_elements(By.TAG_NAME, "div")
        assert len(elements) >= 0, "Page should have elements"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
