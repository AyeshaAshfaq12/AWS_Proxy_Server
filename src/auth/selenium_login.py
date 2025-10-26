from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import random
import os

def get_stealthwriter_cookies(email, password):
    options = webdriver.ChromeOptions()
    
    # Enhanced anti-detection options
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Add headless mode if environment variable is set
    if os.getenv("SELENIUM_HEADLESS", "false").lower() == "true":
        options.add_argument("--headless=new")
    
    driver = webdriver.Chrome(options=options)
    
    # Remove automation indicators
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        print("Navigating to StealthWriter.ai login page...")
        driver.get("https://app.stealthwriter.ai/auth/sign-in")
        
        # Random delay to appear more human-like
        time.sleep(random.uniform(2, 4))
        
        # Wait for and fill email field
        print("Filling email field...")
        email_input = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.ID, "email"))
        )
        
        # Human-like typing
        _human_type(email_input, email)
        time.sleep(random.uniform(1, 2))
        
        # Wait for and fill password field
        print("Filling password field...")
        password_input = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.ID, "password"))
        )
        
        _human_type(password_input, password)
        time.sleep(random.uniform(1, 2))
        
        # Wait for Turnstile to complete (longer timeout)
        print("Waiting for Cloudflare Turnstile to complete...")
        
        # First wait for the submit button to exist
        submit_button = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button[type='submit']"))
        )
        
        # Then wait for it to become enabled (Turnstile completion)
        login_btn = WebDriverWait(driver, 120).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        
        # Additional wait to ensure Turnstile is fully completed
        time.sleep(random.uniform(2, 4))
        
        print("Clicking login button...")
        # Use ActionChains for more human-like clicking
        ActionChains(driver).move_to_element(login_btn).pause(0.5).click().perform()
        
        # Wait for successful login (dashboard or redirect)
        print("Waiting for login to complete...")
        WebDriverWait(driver, 45).until(
            lambda d: "/dashboard" in d.current_url or 
                     "/app" in d.current_url or 
                     "dashboard" in d.page_source.lower()
        )
        
        print("Login successful! Extracting cookies...")
        cookies = driver.get_cookies()
        
        if not cookies:
            raise Exception("No cookies found after login")
        
        print(f"Extracted {len(cookies)} cookies")
        return cookies
        
    except Exception as e:
        # Save page source for debugging
        try:
            error_file = f"selenium_error_{int(time.time())}.html"
            with open(error_file, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"Error page saved to {error_file}")
            print(f"Current URL: {driver.current_url}")
        except:
            pass
        
        raise Exception(f"Login failed: {str(e)}")
    
    finally:
        driver.quit()

def _human_type(element, text):
    """Simulate human-like typing with random delays"""
    element.clear()
    time.sleep(random.uniform(0.1, 0.3))
    
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))
    
    # Random pause after typing
    time.sleep(random.uniform(0.2, 0.5))
