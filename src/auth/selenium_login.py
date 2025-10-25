from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
import os

def get_stealthwriter_cookies(email, password):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    driver.get("https://app.stealthwriter.ai/auth/sign-in")
    time.sleep(2)

    # Fill in email and password
    driver.find_element(By.NAME, "email").send_keys(email)
    driver.find_element(By.NAME, "password").send_keys(password)

    # Wait for Cloudflare Turnstile (may need to increase sleep)
    time.sleep(10)

    # Submit the form
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    time.sleep(5)

    # Go to dashboard to confirm login
    driver.get("https://app.stealthwriter.ai/dashboard")
    time.sleep(2)

    # Extract cookies
    cookies = driver.get_cookies()
    driver.quit()
    return cookies
