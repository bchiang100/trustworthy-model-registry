# Selenium Testing Setup

This project includes Selenium WebDriver tests for automated frontend testing.

## Installation

Install Selenium and dev dependencies:
```bash
pip install -e .[dev]
```

## WebDriver Setup

### Chrome (Recommended)
1. Install Chrome browser
2. ChromeDriver is automatically managed by Selenium 4.15+

### Alternative: Use webdriver-manager
```bash
pip install webdriver-manager
```

Then in your test code:
```python
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)
```

## Running Tests

### Frontend Server
Start the frontend server first:
```bash
cd src/acme_cli/frontend
python3 -m http.server 8001
```

### Run Selenium Tests
```bash
# Run all frontend tests
pytest tests/test_selenium_frontend.py

# Run with verbose output
pytest tests/test_selenium_frontend.py -v

# Run specific test class
pytest tests/test_selenium_frontend.py::TestFrontendNavigation

# Run in headed mode (see browser)
pytest tests/test_selenium_frontend.py --headed
```

### Manual Demo
```bash
# Interactive demo
python selenium_example.py
```

## Test Structure

### `tests/test_selenium_frontend.py`
- **TestFrontendNavigation**: Page navigation and routing
- **TestFrontendFunctionality**: Form interactions and features
- **TestFrontendPerformance**: Load times and resource loading
- **TestFrontendIntegration**: API connectivity (when backend available)

### `selenium_example.py`
Interactive demo script showing:
- Basic page navigation
- Screenshot capture
- Responsive design testing
- JavaScript execution
- All pages testing

## Configuration

### Headless Mode
Tests run in headless mode by default for CI/CD. To see the browser:

```python
chrome_options = Options()
# Remove this line to see browser
# chrome_options.add_argument("--headless")
```

### Timeouts
- Implicit wait: 10 seconds
- Explicit waits: 10 seconds (configurable)

### Screenshots
Failed tests automatically capture screenshots in `screenshots/` directory.

## Best Practices

1. **Page Object Pattern**: For complex UIs, use page objects
2. **Explicit Waits**: Use WebDriverWait for dynamic content
3. **Data Attributes**: Add `data-testid` attributes for reliable element selection
4. **Cleanup**: Always call `driver.quit()` in finally blocks or fixtures

## Troubleshooting

### Common Issues

1. **ChromeDriver not found**
   ```bash
   pip install webdriver-manager
   ```

2. **Port already in use**
   ```bash
   # Kill process on port 8001
   lsof -ti:8001 | xargs kill
   ```

3. **Elements not found**
   - Check if page is fully loaded
   - Use explicit waits
   - Verify element selectors

### Debug Mode
```python
# Add these options for debugging
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
chrome_options.add_experimental_option('useAutomationExtension', False)
```

## CI/CD Integration

For GitHub Actions:
```yaml
- name: Install Chrome
  uses: browser-actions/setup-chrome@latest

- name: Run Selenium tests
  run: |
    python -m http.server 8001 --directory src/acme_cli/frontend &
    sleep 5
    pytest tests/test_selenium_frontend.py
```