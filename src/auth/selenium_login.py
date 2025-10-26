from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import random
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.helpers import structured_log, log_error

def configure_chrome_options():
    """Configure Chrome options for stealth mode"""
    options = Options()
    
    # Headless mode
    if os.getenv("HEADLESS_MODE", "true").lower() == "true":
        options.add_argument("--headless=new")
    
    # Essential Chrome arguments
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    
    # Stealth options
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Realistic user agent
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    
    # Additional stealth options
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    
    # Performance options
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-default-apps")
    
    # Preferences
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False
    }
    options.add_experimental_option("prefs", prefs)
    
    return options

def apply_stealth_scripts(driver):
    """Apply JavaScript to make browser appear more human"""
    try:
        # Remove webdriver flag
        driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        
        # Override navigator properties
        driver.execute_script("""
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)
        
        driver.execute_script("""
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
        """)
        
        # Chrome-specific overrides
        driver.execute_script("""
            window.chrome = {
                runtime: {}
            };
        """)
        
        structured_log("Stealth scripts applied successfully")
    except Exception as e:
        log_error("Stealth Script Error", "Failed to apply stealth scripts", error=str(e))

def human_type(element, text, min_delay=0.05, max_delay=0.15):
    """Type text with human-like delays"""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(min_delay, max_delay))

def random_delay(min_sec=0.5, max_sec=2.0):
    """Random delay to appear more human"""
    time.sleep(random.uniform(min_sec, max_sec))

def wait_for_cloudflare_challenge(driver, timeout=15):
    """
    Wait for Cloudflare challenge to complete
    Returns True if challenge detected and resolved, False if no challenge
    """
    try:
        structured_log("Checking for Cloudflare challenge")
        
        # Check for Cloudflare challenge indicators
        cloudflare_selectors = [
            (By.ID, "challenge-form"),
            (By.CLASS_NAME, "cf-challenge-running"),
            (By.XPATH, "//*[contains(text(), 'Checking your browser')]"),
            (By.XPATH, "//*[contains(text(), 'verify you are human')]")
        ]
        
        challenge_detected = False
        for by, selector in cloudflare_selectors:
            try:
                element = driver.find_element(by, selector)
                if element:
                    challenge_detected = True
                    structured_log("Cloudflare challenge detected", selector=selector)
                    break
            except NoSuchElementException:
                continue
        
        if challenge_detected:
            structured_log("Waiting for Cloudflare challenge to resolve", timeout=timeout)
            time.sleep(timeout)
            structured_log("Cloudflare challenge wait complete")
            return True
        else:
            structured_log("No Cloudflare challenge detected")
            return False
            
    except Exception as e:
        log_error("Cloudflare Check Error", "Error checking for Cloudflare", error=str(e))
        return False

def take_screenshot(driver, filename_prefix="error"):
    """Take screenshot for debugging"""
    try:
        screenshot_dir = os.getenv("SCREENSHOT_DIR", "/tmp/screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filepath = os.path.join(screenshot_dir, f"{filename_prefix}_{timestamp}.png")
        
        driver.save_screenshot(filepath)
        structured_log("Screenshot saved", filepath=filepath)
        return filepath
    except Exception as e:
        log_error("Screenshot Error", "Failed to save screenshot", error=str(e))
        return None

def get_stealthwriter_cookies(email, password, max_retries=None):
    """
    Authenticate with StealthWriter and return cookies
    Handles Cloudflare Turnstile challenge
    
    Args:
        email: User email
        password: User password
        max_retries: Maximum retry attempts (default from env or 3)
    
    Returns:
        List of cookie dictionaries
    """
    if max_retries is None:
        max_retries = int(os.getenv("SELENIUM_MAX_RETRIES", "3"))
    
    timeout = int(os.getenv("SELENIUM_TIMEOUT", "90"))
    
    structured_log(
        "Starting authentication",
        max_retries=max_retries,
        timeout=timeout
    )
    
    for attempt in range(max_retries):
        driver = None
        try:
            structured_log(
                "Authentication attempt",
                attempt=attempt + 1,
                max_retries=max_retries
            )
            
            # Configure Chrome
            options = configure_chrome_options()
            driver = webdriver.Chrome(options=options)
            
            # Apply stealth scripts
            apply_stealth_scripts(driver)
            
            # Navigate to login page
            structured_log("Loading login page")
            driver.get("https://app.stealthwriter.ai/auth/sign-in")
            
            # Initial random delay
            random_delay(2, 4)
            
            # Wait for and handle Cloudflare challenge
            wait_for_cloudflare_challenge(driver, timeout=10)
            
            # Wait for email field
            structured_log("Waiting for login form")
            try:
                email_input = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.NAME, "email"))
                )
                structured_log("Email field found")
            except TimeoutException:
                structured_log("Email field not found, taking screenshot")
                take_screenshot(driver, "email_field_timeout")
                raise Exception("Timeout: Email input not found")
            
            # Wait for password field
            try:
                password_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.NAME, "password"))
                )
                structured_log("Password field found")
            except TimeoutException:
                take_screenshot(driver, "password_field_timeout")
                raise Exception("Timeout: Password input not found")
            
            # Type credentials with human-like behavior
            structured_log("Entering credentials")
            human_type(email_input, email, 0.05, 0.15)
            random_delay(0.3, 0.7)
            human_type(password_input, password, 0.05, 0.15)
            random_delay(0.5, 1.5)
            
            # Wait for login button to be enabled (Turnstile completion)
            structured_log("Waiting for Turnstile challenge to complete")
            try:
                login_btn = WebDriverWait(driver, timeout).until(
                    lambda d: d.find_element(By.XPATH, "//button[@type='submit' and not(@disabled)]")
                )
                structured_log("Login button enabled")
            except TimeoutException:
                take_screenshot(driver, "turnstile_timeout")
                raise Exception("Timeout: Login button still disabled - Turnstile not completed")
            
            # Click login with random delay
            random_delay(0.5, 1.0)
            structured_log("Clicking login button")
            login_btn.click()
            
            # Wait for successful login
            structured_log("Waiting for dashboard redirect")
            try:
                WebDriverWait(driver, 30).until(
                    lambda d: "/dashboard" in d.current_url or "/app" in d.current_url
                )
                structured_log("Login successful", current_url=driver.current_url)
            except TimeoutException:
                take_screenshot(driver, "dashboard_timeout")
                current_url = driver.current_url
                
                # Check if still on login page (failed login)
                if "/sign-in" in current_url:
                    raise Exception("Login failed: Still on login page - check credentials")
                else:
                    # Might be on a different page, try to proceed
                    structured_log("Not on expected dashboard, but not on login page either", url=current_url)
            
            # Let page fully load
            random_delay(2, 3)
            
            # Extract cookies
            structured_log("Extracting cookies")
            cookies = driver.get_cookies()
            
            if not cookies:
                raise Exception("No cookies extracted after login")
            
            structured_log(
                "Authentication successful",
                cookies_count=len(cookies),
                attempt=attempt + 1
            )
            
            # Close driver
            driver.quit()
            
            return cookies
            
        except TimeoutException as e:
            error_msg = f"Timeout on attempt {attempt + 1}: {str(e)}"
            log_error("Selenium Timeout", error_msg, attempt=attempt + 1)
            
            if driver:
                take_screenshot(driver, f"timeout_attempt_{attempt + 1}")
                try:
                    structured_log("Current page source (first 500 chars)", 
                                 source=driver.page_source[:500])
                except:
                    pass
                driver.quit()
            
            if attempt == max_retries - 1:
                raise Exception(f"Failed after {max_retries} attempts: {error_msg}")
            
            # Exponential backoff with jitter
            wait_time = (2 ** attempt) * random.uniform(1, 2)
            structured_log(f"Retrying in {wait_time:.1f} seconds", 
                         attempt=attempt + 1, 
                         max_retries=max_retries)
            time.sleep(wait_time)
            
        except WebDriverException as e:
            error_msg = f"WebDriver error on attempt {attempt + 1}: {str(e)}"
            log_error("WebDriver Error", error_msg, attempt=attempt + 1)
            
            if driver:
                driver.quit()
            
            if attempt == max_retries - 1:
                raise Exception(f"WebDriver error after {max_retries} attempts: {str(e)}")
            
            time.sleep(random.uniform(2, 4))
            
        except Exception as e:
            error_msg = f"Unexpected error on attempt {attempt + 1}: {str(e)}"
            log_error(
                "Authentication Error", 
                error_msg,
                attempt=attempt + 1,
                error_type=type(e).__name__
            )
            
            if driver:
                take_screenshot(driver, f"error_attempt_{attempt + 1}")
                driver.quit()
            
            if attempt == max_retries - 1:
                raise Exception(f"Failed after {max_retries} attempts: {str(e)}")
            
            time.sleep(random.uniform(2, 4))
    
    raise Exception(f"Failed to authenticate after {max_retries} retry attempts")

def validate_cookies(cookies):
    """
    Validate that cookies contain necessary session information
    
    Args:
        cookies: List of cookie dictionaries
        
    Returns:
        Boolean indicating if cookies are valid
    """
    if not cookies:
        return False
    
    # Check for common session cookie names
    cookie_names = [cookie['name'] for cookie in cookies]
    structured_log("Validating cookies", cookie_names=cookie_names)
    
    # Add your specific cookie validation logic here
    # For example, check for specific cookie names that indicate a valid session
    
    return len(cookies) > 0

if __name__ == "__main__":
    # Test the authentication
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python selenium_login.py <email> <password>")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    try:
        cookies = get_stealthwriter_cookies(email, password)
        print(f"Successfully retrieved {len(cookies)} cookies")
        for cookie in cookies:
            print(f"  - {cookie['name']}: {cookie['value'][:20]}...")
    except Exception as e:
        print(f"Failed to authenticate: {str(e)}")
        sys.exit(1)
