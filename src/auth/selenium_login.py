from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def get_stealthwriter_cookies(email, password):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    driver.get("https://app.stealthwriter.ai/auth/sign-in")

    # Wait for Cloudflare challenge to pass (page may reload)
    max_wait = 60
    found = False
    for _ in range(max_wait // 2):
        time.sleep(2)
        # Try to find the email field in main document
        try:
            email_input = driver.find_element(By.NAME, "email")
            found = True
            break
        except:
            pass
        # Try to find the email field in iframes
        for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
            driver.switch_to.frame(iframe)
            try:
                email_input = driver.find_element(By.NAME, "email")
                found = True
                break
            except:
                driver.switch_to.default_content()
        if found:
            break
        driver.switch_to.default_content()
    if not found:
        driver.quit()
        raise Exception("Timeout: Email input not found. Cloudflare or page structure may have changed.")

    # Fill in credentials
    email_input.send_keys(email)
    driver.find_element(By.NAME, "password").send_keys(password)

    # Wait for Turnstile (Cloudflare) widget to complete
    time.sleep(10)

    # Submit the form
    submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
    submit_btn.click()

    # Wait for dashboard to load
    WebDriverWait(driver, 30).until(
        EC.url_contains("/dashboard")
    )

    # Extract cookies
    cookies = driver.get_cookies()
    driver.quit()
    return cookies
