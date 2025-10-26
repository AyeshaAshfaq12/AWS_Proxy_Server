from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
import time
import os
import tempfile
import uuid
import subprocess
import json
import signal
import random

def manual_login_and_capture_cookies():
    """
    Opens a browser window for manual login and captures cookies after successful login
    """
    print("🚀 Starting manual login process...")
    
    # Check for VNC if needed
    if os.getenv("DISPLAY") and not os.getenv("SELENIUM_HEADLESS", "false").lower() == "true":
        print(f"📺 Using display: {os.getenv('DISPLAY')}")
        print("💡 If you need to see the browser, you can:")
        print("   1. Use VNC to connect to this server")
        print("   2. Or set SELENIUM_HEADLESS=false and use X11 forwarding")
    
    # Try to start Xvfb if not running and DISPLAY is set
    if os.getenv("DISPLAY"):
        try:
            subprocess.run(["pgrep", "Xvfb"], check=True, capture_output=True)
            print("✅ Xvfb already running")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("🔄 Starting Xvfb...")
            try:
                subprocess.Popen([
                    "Xvfb", os.getenv("DISPLAY"), "-screen", "0", "1920x1080x24"
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2)
                print("✅ Xvfb started")
            except FileNotFoundError:
                print("⚠️  Xvfb not found, proceeding without virtual display")
    
    options = webdriver.ChromeOptions()
    
    # Create unique user data directory for each session
    temp_dir = tempfile.gettempdir()
    unique_id = str(uuid.uuid4())
    user_data_dir = os.path.join(temp_dir, f"chrome_manual_{unique_id}")
    
    # Enhanced options for manual browsing
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Check if we should use headless mode
    use_headless = os.getenv("SELENIUM_HEADLESS", "false").lower() == "true"
    has_display = bool(os.getenv("DISPLAY"))
    
    if use_headless and not has_display:
        print("🤖 Running in headless mode - you won't see the browser")
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
    elif has_display:
        # Use virtual display
        options.add_argument(f"--display={os.getenv('DISPLAY')}")
        print(f"🖥️  Using virtual display: {os.getenv('DISPLAY')}")
    else:
        print("🌐 Running with visible browser window")
    
    # Common options for stability
    options.add_argument("--window-size=1200,800")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-backgrounding-occluded-windows")
    
    driver = None
    try:
        print("🌐 Opening Chrome browser...")
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(60)
        
        # Remove automation indicators
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_script("window.chrome = { runtime: {} };")
        driver.execute_script("delete navigator.__webdriver_script_fn;")
        
        print("🔗 Navigating to StealthWriter.ai login page...")
        driver.get("https://app.stealthwriter.ai/auth/sign-in")
        
        # Wait for page to load
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "email"))
        )
        
        print("\n" + "="*70)
        print("🎯 MANUAL LOGIN REQUIRED")
        print("="*70)
        print("The browser should now be open with the StealthWriter.ai login page.")
        print("")
        print("📋 STEPS TO COMPLETE:")
        print("1. Enter your email and password in the browser")
        print("2. Complete the Cloudflare Turnstile challenge (checkbox)")
        print("3. Click the Login button")
        print("4. Wait until you reach the dashboard/main page")
        print("5. Then press Enter in this terminal")
        print("")
        print("🔍 CURRENT PAGE INFO:")
        print(f"   URL: {driver.current_url}")
        print(f"   Title: {driver.title}")
        print("")
        if use_headless:
            print("⚠️  RUNNING IN HEADLESS MODE - You cannot see the browser!")
            print("   To enable visual mode, set SELENIUM_HEADLESS=false")
        print("="*70)
        
        # Wait for manual completion with timeout
        print("\n⏳ Waiting for manual login completion...")
        print("   Type 'status' to check current page")
        print("   Type 'quit' to abort")
        print("   Press Enter when login is complete")
        
        while True:
            try:
                user_input = input("\n⌨️  Press Enter after login completion (or 'status'/'quit'): ").strip().lower()
                
                if user_input == 'quit':
                    raise Exception("Manual login aborted by user")
                elif user_input == 'status':
                    print(f"📍 Current URL: {driver.current_url}")
                    print(f"📄 Page Title: {driver.title}")
                    
                    # Check for login indicators
                    page_source = driver.page_source.lower()
                    if "dashboard" in page_source or "welcome" in page_source:
                        print("✅ Looks like you're logged in!")
                    elif "sign-in" in driver.current_url:
                        print("⏳ Still on login page")
                    else:
                        print("❓ Unknown page state")
                    continue
                elif user_input == '' or user_input == 'done':
                    break
                else:
                    print("⚠️  Enter 'status', 'quit', or just press Enter")
                    
            except KeyboardInterrupt:
                raise Exception("Manual login interrupted by user")
        
        # Verify we're logged in by checking URL or page content
        current_url = driver.current_url
        page_source = driver.page_source.lower()
        
        print(f"\n🔍 Checking login status...")
        print(f"   Current URL: {current_url}")
        
        # Multiple ways to detect successful login
        login_indicators = [
            "dashboard" in current_url,
            "app.stealthwriter.ai" in current_url and "sign-in" not in current_url,
            "dashboard" in page_source,
            "welcome" in page_source,
            "logout" in page_source,
            current_url != "https://app.stealthwriter.ai/auth/sign-in"
        ]
        
        if any(login_indicators):
            print("✅ Login detected! Extracting cookies...")
            cookies = driver.get_cookies()
            
            if not cookies:
                print("⏳ No cookies found, waiting 3 seconds...")
                time.sleep(3)
                cookies = driver.get_cookies()
            
            if cookies:
                # Filter valid cookies
                valid_cookies = [cookie for cookie in cookies if cookie.get('name') and cookie.get('value')]
                
                if valid_cookies:
                    print(f"🍪 Successfully captured {len(valid_cookies)} cookies")
                    
                    # Save cookies with timestamp
                    cookies_data = {
                        "timestamp": time.time(),
                        "url": current_url,
                        "user_agent": driver.execute_script("return navigator.userAgent"),
                        "cookies": valid_cookies
                    }
                    
                    # Save to file for persistence
                    cookies_file = "manual_login_cookies.json"
                    with open(cookies_file, "w") as f:
                        json.dump(cookies_data, f, indent=2)
                    
                    print(f"💾 Cookies saved to {cookies_file}")
                    
                    # Log cookie names (not values for security)
                    cookie_names = [cookie['name'] for cookie in valid_cookies]
                    print(f"🏷️  Cookie names: {cookie_names}")
                    
                    # Show important cookies
                    important_cookies = [c for c in valid_cookies if any(
                        keyword in c['name'].lower() 
                        for keyword in ['session', 'auth', 'token', 'csrf', 'user']
                    )]
                    
                    if important_cookies:
                        print(f"🔑 Important cookies found: {[c['name'] for c in important_cookies]}")
                    
                    return valid_cookies
                else:
                    raise Exception("No valid cookies found after login")
            else:
                raise Exception("No cookies found after login")
        else:
            print(f"❌ Login not detected. Current URL: {current_url}")
            print("Please ensure you are logged in and on the dashboard page")
            
            # Show page title for debugging
            try:
                title = driver.title
                print(f"📄 Page title: {title}")
            except:
                pass
            
            raise Exception("Login verification failed - not on dashboard page")
            
    except Exception as e:
        # Save debug info
        try:
            timestamp = int(time.time())
            error_file = f"manual_login_error_{timestamp}.html"
            screenshot_file = f"manual_login_error_{timestamp}.png"
            
            if driver:
                try:
                    with open(error_file, "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    print(f"📄 Page source saved: {error_file}")
                except Exception as save_error:
                    print(f"❌ Could not save page source: {save_error}")
                
                try:
                    driver.save_screenshot(screenshot_file)
                    print(f"📸 Screenshot saved: {screenshot_file}")
                except Exception as ss_error:
                    print(f"❌ Could not save screenshot: {ss_error}")
                
                try:
                    print(f"🌐 Final URL: {driver.current_url}")
                    print(f"📄 Final Title: {driver.title}")
                except:
                    pass
        except Exception as debug_error:
            print(f"❌ Debug save failed: {debug_error}")
        
        raise Exception(f"Manual login failed: {str(e)}")
    
    finally:
        if driver:
            print("🔄 Keeping browser open for 5 more seconds...")
            time.sleep(5)
            try:
                driver.quit()
                print("✅ Browser closed")
            except Exception as quit_error:
                print(f"⚠️  Error closing browser: {quit_error}")
                # Force kill if needed
                try:
                    if hasattr(driver, 'service') and driver.service.process:
                        os.kill(driver.service.process.pid, signal.SIGTERM)
                except:
                    pass
        
        # Cleanup
        try:
            import shutil
            if os.path.exists(user_data_dir):
                shutil.rmtree(user_data_dir, ignore_errors=True)
        except Exception as cleanup_error:
            print(f"⚠️  Cleanup error: {cleanup_error}")

def load_manual_cookies():
    """
    Load cookies from manual login file
    """
    try:
        cookies_file = "manual_login_cookies.json"
        
        if not os.path.exists(cookies_file):
            return None
        
        with open(cookies_file, "r") as f:
            cookies_data = json.load(f)
        
        # Check if cookies are still relatively fresh (within 24 hours)
        cookie_age = time.time() - cookies_data["timestamp"]
        max_age = 86400  # 24 hours
        
        if cookie_age > max_age:
            print(f"⏰ Manual cookies are {cookie_age/3600:.1f} hours old (max {max_age/3600} hours)")
            return None
        
        cookies = cookies_data["cookies"]
        print(f"✅ Loaded {len(cookies)} manual cookies (age: {cookie_age/3600:.1f} hours)")
        
        return cookies
        
    except Exception as e:
        print(f"❌ Failed to load manual cookies: {e}")
        return None

def get_manual_cookie_status():
    """
    Get status of manual cookies
    """
    try:
        cookies_file = "manual_login_cookies.json"
        
        if not os.path.exists(cookies_file):
            return {"exists": False, "message": "No manual cookies file found"}
        
        with open(cookies_file, "r") as f:
            cookies_data = json.load(f)
        
        cookie_age = time.time() - cookies_data["timestamp"]
        max_age = 86400  # 24 hours
        
        return {
            "exists": True,
            "count": len(cookies_data["cookies"]),
            "age_hours": cookie_age / 3600,
            "max_age_hours": max_age / 3600,
            "expired": cookie_age > max_age,
            "url": cookies_data.get("url", "unknown"),
            "timestamp": cookies_data["timestamp"]
        }
        
    except Exception as e:
        return {"exists": False, "error": str(e)}

# Keep the original function for backward compatibility
def get_stealthwriter_cookies(email, password):
    """
    This function now loads manual cookies or prompts for manual login
    """
    print("🔄 Checking for existing manual login cookies...")
    
    # Try to load existing manual cookies first
    cookies = load_manual_cookies()
    if cookies:
        print(f"✅ Using {len(cookies)} cookies from manual login")
        return cookies
    
    print("❌ No valid manual cookies found")
    print("🎯 Manual login required")
    print("   Run: POST /manual-login endpoint")
    print("   Or call: manual_login_and_capture_cookies() function")
    
    raise Exception("No valid cookies available. Please complete manual login first using /manual-login endpoint.")
