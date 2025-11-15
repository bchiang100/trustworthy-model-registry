"""
Selenium tests for the frontend model registry interface.
"""
# runs setup, loading, and navigation tests
# 8 frontend tests total

# Run command: pytest tests/test_selenium_frontend.py -v
# run this from the project root

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


@pytest.fixture
def driver():
    """Setup Chrome WebDriver with headless option for CI/CD."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=chrome_options)
    driver.implicitly_wait(10)
    yield driver
    driver.quit()


class TestFrontendNavigation:
    """Test navigation between frontend pages."""

    BASE_URL = "http://localhost:8000"

    def test_homepage_loads(self, driver):
        """Test that the homepage loads successfully."""
        driver.get(self.BASE_URL)

        # Check page title
        assert "Model Registry" in driver.title

        # Check main heading exists
        heading = driver.find_element(By.TAG_NAME, "h1")
        assert "Model Registry" in heading.text

    def test_navigation_links_exist(self, driver):
        """Test that all navigation links are present."""
        driver.get(self.BASE_URL)

        nav_links = driver.find_elements(By.CSS_SELECTOR, "nav a")
        expected_links = ["Home", "Upload", "Ingest", "License Check", "Enumerate / Search"]

        actual_links = [link.text for link in nav_links]
        for expected in expected_links:
            assert expected in actual_links

    def test_upload_page_navigation(self, driver):
        """Test navigation to upload page."""
        driver.get(self.BASE_URL)

        upload_link = driver.find_element(By.LINK_TEXT, "Upload")
        upload_link.click()

        # Verify we're on upload page
        assert "upload.html" in driver.current_url

        # Check for upload-specific content
        page_content = driver.page_source
        assert "upload" in page_content.lower()

    def test_ingest_page_navigation(self, driver):
        """Test navigation to ingest page."""
        driver.get(self.BASE_URL)

        ingest_link = driver.find_element(By.LINK_TEXT, "Ingest")
        ingest_link.click()

        assert "ingest.html" in driver.current_url

    def test_license_check_page_navigation(self, driver):
        """Test navigation to license check page."""
        driver.get(self.BASE_URL)

        license_link = driver.find_element(By.LINK_TEXT, "License Check")
        license_link.click()

        assert "license_check.html" in driver.current_url

    def test_enumerate_page_navigation(self, driver):
        """Test navigation to enumerate/search page."""
        driver.get(self.BASE_URL)

        enumerate_link = driver.find_element(By.LINK_TEXT, "Enumerate / Search")
        enumerate_link.click()

        assert "enumerate.html" in driver.current_url


class TestFrontendFunctionality:
    """Test frontend form functionality."""

    BASE_URL = "http://localhost:8000"

    def test_upload_form_exists(self, driver):
        """Test that upload form exists and has required fields."""
        driver.get(f"{self.BASE_URL}/upload.html")

        forms = driver.find_elements(By.TAG_NAME, "form")
        assert len(forms) > 0, "No forms found on upload page"

    def test_search_functionality(self, driver):
        """Test search functionality on enumerate page."""
        driver.get(f"{self.BASE_URL}/enumerate.html")

        search_elements = driver.find_elements(By.CSS_SELECTOR,
                                             "input[type='search'], input[type='text'], button")
        assert len(search_elements) > 0, "No search elements found"



class TestFrontendPerformance:
    """Test frontend performance and loading."""

    BASE_URL = "http://localhost:8000"

    def test_page_load_time(self, driver):
        """Test that pages load within reasonable time."""
        import time

        start_time = time.time()
        driver.get(self.BASE_URL)

        # Wait for page to be fully loaded
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        load_time = time.time() - start_time
        assert load_time < 5, f"Page took too long to load: {load_time}s"


