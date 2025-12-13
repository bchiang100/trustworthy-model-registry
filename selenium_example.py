"""
Example Selenium script for manual testing of the frontend.
Run this script to see Selenium in action (non-headless mode).

Usage:
    python selenium_example.py

Requirements:
    - Chrome browser installed
    - ChromeDriver in PATH or use webdriver-manager
    - Frontend server running on localhost:8001
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


def main():
    """Demonstrate Selenium functionality with the frontend."""
    print("Starting Selenium demo...")

    # Setup Chrome driver (visible browser window)
    driver = webdriver.Chrome()
    driver.implicitly_wait(10)

    try:
        print("1. Loading homepage...")
        driver.get("http://localhost:8001")

        # Take screenshot
        driver.save_screenshot("homepage.png")
        print("   Screenshot saved: homepage.png")

        # Verify page loaded
        title = driver.title
        print(f"   Page title: {title}")

        print("2. Testing navigation...")
        nav_links = driver.find_elements(By.CSS_SELECTOR, "nav a")
        print(f"   Found {len(nav_links)} navigation links")

        for link in nav_links:
            print(f"   - {link.text}")

        print("3. Navigating to Upload page...")
        upload_link = driver.find_element(By.LINK_TEXT, "Upload")
        upload_link.click()
        time.sleep(2)

        current_url = driver.current_url
        print(f"   Current URL: {current_url}")

        print("4. Taking screenshot of Upload page...")
        driver.save_screenshot("upload_page.png")
        print("   Screenshot saved: upload_page.png")

        print("5. Testing back navigation...")
        driver.back()
        time.sleep(2)

        print("6. Checking page responsiveness...")
        # Test mobile viewport
        driver.set_window_size(375, 667)
        time.sleep(1)
        driver.save_screenshot("mobile_view.png")
        print("   Mobile screenshot saved: mobile_view.png")

        # Restore desktop viewport
        driver.set_window_size(1200, 800)
        time.sleep(1)

        print("7. Testing JavaScript execution...")
        page_height = driver.execute_script("return document.body.scrollHeight;")
        print(f"   Page height: {page_height}px")

        print("\nSelenium demo completed successfully!")
        print("Screenshots saved: homepage.png, upload_page.png, mobile_view.png")

    except Exception as e:
        print(f"Error during demo: {e}")

    finally:
        print("Closing browser...")
        driver.quit()


def test_all_pages():
    """Test all pages in the frontend."""
    pages = [
        ("Home", "index.html"),
        ("Upload", "upload.html"),
        ("Ingest", "ingest.html"),
        ("License Check", "license_check.html"),
        ("Enumerate", "enumerate.html")
    ]

    driver = webdriver.Chrome()
    driver.implicitly_wait(10)

    try:
        for page_name, page_file in pages:
            print(f"Testing {page_name} page...")

            if page_file == "index.html":
                driver.get("http://localhost:8001")
            else:
                driver.get(f"http://localhost:8001/{page_file}")

            # Verify page loads
            title = driver.title
            print(f"  Title: {title}")

            # Check for common elements
            try:
                header = driver.find_element(By.TAG_NAME, "header")
                print(f"  Header found: {header.tag_name}")
            except:
                print("  No header found")

            # Take screenshot
            screenshot_name = f"{page_name.lower().replace(' ', '_')}_page.png"
            driver.save_screenshot(screenshot_name)
            print(f"  Screenshot: {screenshot_name}")

            time.sleep(1)

    finally:
        driver.quit()


if __name__ == "__main__":
    choice = input("Choose demo: (1) Basic demo, (2) All pages test: ").strip()

    if choice == "2":
        test_all_pages()
    else:
        main()