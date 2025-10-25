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

    # Wait for email and password fields
    try:
        email_input = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        password_input = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.NAME, "password"))
        )
    except Exception:
        driver.quit()
        raise Exception("Timeout: Email or password input not found. Cloudflare or page structure may have changed.")

    email_input.send_keys(email)
    password_input.send_keys(password)

    # Wait for login button to become enabled (Turnstile must complete)
    try:
        login_btn = WebDriverWait(driver, 60).until(
            lambda d: d.find_element(By.XPATH, "//button[@type='submit' and not(@disabled)]")
        )
    except Exception:
        driver.quit()
        raise Exception("Timeout: Login button is still disabled. Cloudflare Turnstile challenge not passed.")

    login_btn.click()

    # Wait for dashboard to load
    try:
        WebDriverWait(driver, 30).until(
            EC.url_contains("/dashboard")
        )
    except Exception:
        driver.quit()
        raise Exception("Login failed or dashboard did not load.")

    cookies = driver.get_cookies()
    driver.quit()
    return cookies
