from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import random
import os
import tempfile
import uuid
import subprocess
import signal

def get_stealthwriter_cookies(email, password):
    # Try to start Xvfb if not running and DISPLAY is set
    if os.getenv("DISPLAY"):
        try:
            subprocess.run(["pgrep", "Xvfb"], check=True, capture_output=True)
            print("Xvfb already running")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Starting Xvfb...")
            try:
                subprocess.Popen([
                    "Xvfb", os.getenv("DISPLAY"), "-screen", "0", "1920x1080x24"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2)
            except FileNotFoundError:
                print("Xvfb not found, proceeding without virtual display")
    
    options = webdriver.ChromeOptions()
    
    # Create unique user data directory for each session
    temp_dir = tempfile.gettempdir()
    unique_id = str(uuid.uuid4())
    user_data_dir = os.path.join(temp_dir, f"chrome_user_data_{unique_id}")
    
    # Enhanced anti-detection options
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Add unique user data directory
    options.add_argument(f"--user-data-dir={user_data_dir}")
    
    # Check if we should use headless mode
    use_headless = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"
    has_display = bool(os.getenv("DISPLAY"))
    
    if use_headless and not has_display:
        # Use headless mode
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--virtual-time-budget=5000")
        options.add_argument("--run-all-compositor-stages-before-draw")
        print("Running in headless mode")
    elif has_display:
        # Use virtual display
        options.add_argument(f"--display={os.getenv('DISPLAY')}")
        print(f"Using virtual display: {os.getenv('DISPLAY')}")
    else:
        # Non-headless mode (for local development)
        print("Running in non-headless mode")
    
    # Common options for server environments - Enhanced for stability
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-default-apps")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-translate")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-ipc-flooding-protection")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--start-maximized")
    
    # Additional stability options
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_argument("--disable-crash-reporter")
    options.add_argument("--disable-logging")
    options.add_argument("--disable-component-update")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-sync")
    options.add_argument("--metrics-recording-only")
    options.add_argument("--no-report-upload")
    options.add_argument("--disable-breakpad")
    
    # Set shorter timeouts for WebDriver
    service = webdriver.ChromeService()
    service.start_timeout = 30  # Reduce startup timeout
    
    driver = None
    start_time = time.time()
    max_total_time = 300  # 5 minutes maximum
    
    try:
        print(f"Starting Chrome with display: {os.environ.get('DISPLAY', 'none')}")
        
        # Create driver with shorter timeout
        driver = webdriver.Chrome(options=options, service=service)
        driver.set_page_load_timeout(60)  # Set page load timeout
        driver.implicitly_wait(10)  # Set implicit wait
        
        # Enhanced stealth mode
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("window.chrome = { runtime: {} };")
        driver.execute_script("delete navigator.__webdriver_script_fn;")
        
        print("Navigating to StealthWriter.ai login page...")
        driver.get("https://app.stealthwriter.ai/auth/sign-in")
        
        # Wait for page to fully load with timeout check
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        time.sleep(random.uniform(2, 3))
        
        # Check if we've exceeded time limit
        if time.time() - start_time > max_total_time:
            raise Exception("Total time limit exceeded")
        
        # Fill email field
        print("Filling email field...")
        email_input = driver.find_element(By.ID, "email")
        _human_type(email_input, email)
        time.sleep(random.uniform(1, 2))
        
        # Fill password field
        print("Filling password field...")
        password_input = driver.find_element(By.ID, "password")
        _human_type(password_input, password)
        time.sleep(random.uniform(1, 2))
        
        # Handle Cloudflare Turnstile - Improved with shorter timeouts and better error handling
        print("Waiting for Cloudflare Turnstile to complete...")
        
        submit_button = None
        turnstile_completed = False
        turnstile_start_time = time.time()
        max_turnstile_time = 120  # 2 minutes for Turnstile
        
        # Method 1: Wait for submit button to be enabled (shorter timeout)
        try:
            print("Waiting for submit button to be enabled...")
            submit_button = WebDriverWait(driver, 60).until(  # Reduced from 120 to 60
                lambda d: d.find_element(By.CSS_SELECTOR, "button[type='submit']").is_enabled()
            )
            turnstile_completed = True
            print("✅ Turnstile completed - submit button enabled!")
        except TimeoutException:
            print("❌ Submit button never became enabled")
        
        # Check time limit for Turnstile
        if time.time() - turnstile_start_time > max_turnstile_time:
            raise Exception("Turnstile timeout - exceeded maximum wait time")
        
        # Method 2: Check for Turnstile response token (if button method failed)
        if not turnstile_completed:
            try:
                print("Checking for Turnstile response token...")
                # Try multiple times with shorter waits
                for attempt in range(3):
                    try:
                        token_result = driver.execute_script(
                            "return document.querySelector('input[name=\"cf-turnstile-response\"]')?.value || ''"
                        )
                        if token_result and len(token_result) > 0:
                            submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                            turnstile_completed = True
                            print("✅ Turnstile completed - found response token!")
                            break
                    except Exception as e:
                        print(f"Token check attempt {attempt + 1} failed: {e}")
                    
                    if attempt < 2:  # Don't sleep on last attempt
                        time.sleep(10)
                        
            except Exception as e:
                print(f"❌ Turnstile token check failed: {e}")
        
        # Method 3: Check if iframe disappeared (last resort)
        if not turnstile_completed and time.time() - turnstile_start_time < max_turnstile_time:
            try:
                print("Checking iframe state...")
                for attempt in range(3):
                    try:
                        iframe_present = driver.execute_script(
                            "return !!document.querySelector('iframe[src*=\"challenges.cloudflare.com\"]')"
                        )
                        if not iframe_present:
                            submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                            turnstile_completed = True
                            print("✅ Turnstile iframe disappeared!")
                            break
                    except Exception as e:
                        print(f"Iframe check attempt {attempt + 1} failed: {e}")
                    
                    if attempt < 2:
                        time.sleep(5)
                        
            except Exception as e:
                print(f"❌ Iframe check failed: {e}")
        
        if not turnstile_completed:
            raise Exception("Failed to complete Turnstile challenge after all methods")
        
        # Check total time limit again
        if time.time() - start_time > max_total_time:
            raise Exception("Total time limit exceeded after Turnstile")
        
        # Additional wait to ensure everything is ready
        time.sleep(random.uniform(1, 2))
        
        # Click the login button with error handling
        print("Clicking login button...")
        login_clicked = False
        
        for click_attempt in range(3):
            try:
                if click_attempt == 0:
                    # Method 1: ActionChains
                    driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
                    time.sleep(0.5)
                    ActionChains(driver).move_to_element(submit_button).pause(0.5).click().perform()
                elif click_attempt == 1:
                    # Method 2: Direct click
                    submit_button.click()
                else:
                    # Method 3: JavaScript click
                    driver.execute_script("arguments[0].click();", submit_button)
                
                login_clicked = True
                print(f"Login button clicked successfully (method {click_attempt + 1})")
                break
                
            except Exception as click_error:
                print(f"Click attempt {click_attempt + 1} failed: {click_error}")
                if click_attempt < 2:
                    time.sleep(1)
        
        if not login_clicked:
            raise Exception("Failed to click login button after all attempts")
        
        print("Login button clicked, waiting for response...")
        time.sleep(2)
        
        # Check for login errors first
        try:
            error_elements = driver.find_elements(By.CSS_SELECTOR, "[role='alert'], .error, .alert-error, .text-red-500, .text-destructive")
            if error_elements:
                error_text = " | ".join([elem.text for elem in error_elements if elem.text.strip()])
                if error_text:
                    raise Exception(f"Login error detected: {error_text}")
        except Exception as e:
            if "Login error detected" in str(e):
                raise e
        
        # Wait for successful login with multiple indicators (shorter timeout)
        print("Waiting for login to complete...")
        login_success = False
        
        try:
            # Reduced timeout from 45 to 30 seconds
            WebDriverWait(driver, 30).until(
                lambda d: (
                    "/dashboard" in d.current_url or 
                    "/app" in d.current_url or
                    "dashboard" in d.page_source.lower() or
                    "welcome" in d.page_source.lower() or
                    d.current_url != "https://app.stealthwriter.ai/auth/sign-in"
                )
            )
            login_success = True
            print(f"✅ Login successful! Current URL: {driver.current_url}")
        except TimeoutException:
            print(f"❌ Login may have failed. Current URL: {driver.current_url}")
            
            # Check if we're still on login page
            if "sign-in" in driver.current_url:
                # Look for specific error indicators
                page_source = driver.page_source.lower()
                if any(indicator in page_source for indicator in ["invalid", "incorrect", "error", "failed"]):
                    raise Exception("Login failed - invalid credentials or other error")
                else:
                    raise Exception("Login timeout - still on login page")
        
        if not login_success:
            raise Exception("Login verification failed")
        
        # Extract cookies after successful login
        print("Extracting cookies...")
        cookies = []
        
        # Try multiple times to get cookies
        for cookie_attempt in range(3):
            try:
                cookies = driver.get_cookies()
                if cookies:
                    break
                print(f"No cookies found on attempt {cookie_attempt + 1}, waiting...")
                time.sleep(1)
            except Exception as e:
                print(f"Cookie extraction attempt {cookie_attempt + 1} failed: {e}")
                if cookie_attempt < 2:
                    time.sleep(1)
        
        if not cookies:
            raise Exception("No cookies found after successful login")
        
        # Filter out empty or invalid cookies
        valid_cookies = [cookie for cookie in cookies if cookie.get('name') and cookie.get('value')]
        
        if not valid_cookies:
            raise Exception("No valid cookies found after login")
        
        print(f"✅ Successfully extracted {len(valid_cookies)} valid cookies")
        
        # Log cookie names for debugging (not values for security)
        cookie_names = [cookie['name'] for cookie in valid_cookies]
        print(f"Cookie names: {cookie_names}")
        
        return valid_cookies
        
    except Exception as e:
        # Enhanced debugging with time tracking
        total_time = time.time() - start_time
        error_info = f"Login failed after {total_time:.1f}s: {str(e)}"
        
        try:
            timestamp = int(time.time())
            error_file = f"selenium_error_{timestamp}.html"
            screenshot_file = f"selenium_error_{timestamp}.png"
            
            if driver:
                try:
                    with open(error_file, "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    print(f"Page source saved: {error_file}")
                except Exception as save_e:
                    print(f"Could not save page source: {save_e}")
                
                try:
                    driver.save_screenshot(screenshot_file)
                    print(f"Screenshot saved: {screenshot_file}")
                except Exception as ss_e:
                    print(f"Could not save screenshot: {ss_e}")
                
                try:
                    print(f"Current URL: {driver.current_url}")
                    
                    # Enhanced debugging information with error handling
                    try:
                        # Check Turnstile state
                        turnstile_token = driver.execute_script(
                            "return document.querySelector('input[name=\"cf-turnstile-response\"]')?.value || 'not found'"
                        )
                        print(f"Turnstile token: {'present' if turnstile_token and turnstile_token != 'not found' else 'missing'}")
                    except:
                        print("Could not check Turnstile token")
                    
                    try:
                        # Check button state
                        button_disabled = driver.execute_script(
                            "return document.querySelector('button[type=\"submit\"]')?.disabled || 'button not found'"
                        )
                        print(f"Submit button disabled: {button_disabled}")
                    except:
                        print("Could not check button state")
                    
                    try:
                        # Check for error messages
                        error_elements = driver.find_elements(By.CSS_SELECTOR, "[role='alert'], .error, .alert-error, .text-red-500, .text-destructive")
                        if error_elements:
                            error_messages = [elem.text for elem in error_elements if elem.text.strip()]
                            print(f"Error messages on page: {error_messages}")
                    except:
                        print("Could not check for error messages")
                    
                    try:
                        # Check if we're logged in but cookies aren't loading
                        if "/dashboard" in driver.current_url or "dashboard" in driver.page_source.lower():
                            print("⚠️  Appears to be logged in but no cookies found - this is unusual")
                    except:
                        print("Could not check login status")
                        
                except Exception as debug_e:
                    print(f"Debug info error: {debug_e}")
        except Exception as save_e:
            print(f"Could not save debug info: {save_e}")
        
        raise Exception(error_info)
    
    finally:
        if driver:
            try:
                # Force quit the driver with timeout
                driver.quit()
            except Exception as quit_error:
                print(f"Error closing driver: {quit_error}")
                # Force kill if normal quit fails
                try:
                    if hasattr(driver, 'service') and driver.service.process:
                        os.kill(driver.service.process.pid, signal.SIGTERM)
                        time.sleep(1)
                        os.kill(driver.service.process.pid, signal.SIGKILL)
                except:
                    pass
        
        # Cleanup temporary directory
        try:
            import shutil
            if os.path.exists(user_data_dir):
                shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception as cleanup_e:
            print(f"Cleanup error: {cleanup_e}")

def _human_type(element, text):
    """Simulate human-like typing with random delays"""
    element.clear()
    time.sleep(random.uniform(0.1, 0.2))  # Reduced delay
    
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.03, 0.08))  # Reduced delay
    
    # Random pause after typing
    time.sleep(random.uniform(0.1, 0.3))  # Reduced delay
