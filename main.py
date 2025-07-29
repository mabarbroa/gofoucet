import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import InvalidElementStateException, TimeoutException
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Fogo address and faucet URL
FOGO_ADDRESS = "addresmu ya rek"
FAUCET_URL = "https://faucet.fogo.io"

# Configure Chrome options
logger.info("Configuring Chrome options")
options = uc.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--window-size=1920,1080")
options.add_argument("--headless=new")  # Comment out and use xvfb if manual verification needed
options.binary_location = "/opt/google/chrome/google-chrome"

def perform_faucet_claim(driver, wait, token_type, attempt):
    max_retries = 3
    retry_delay = 5  # Seconds to wait before retrying

    for retry in range(max_retries):
        try:
            logger.info(f"Attempt {attempt} (Retry {retry + 1}/{max_retries}): Current page URL: {driver.current_url}")
            
            # Wait for JavaScript to settle
            time.sleep(5)
            
            logger.info(f"Attempt {attempt}: Waiting for form to load")
            pubkey_input = wait.until(EC.element_to_be_clickable((By.NAME, "pubkey")))
            logger.info(f"Attempt {attempt}: Form loaded successfully")
            logger.info(f"Attempt {attempt}: Filling in Fogo address")
            
            # Use JavaScript for input to avoid state issues
            logger.info(f"Attempt {attempt}: Pubkey input enabled: {pubkey_input.is_enabled()}, displayed: {pubkey_input.is_displayed()}")
            try:
                pubkey_input.clear()
                pubkey_input.send_keys(FOGO_ADDRESS)
            except InvalidElementStateException:
                logger.warning(f"Attempt {attempt}: Failed to clear/input via Selenium, using JavaScript")
                driver.execute_script("arguments[0].value = '';", pubkey_input)
                driver.execute_script(f"arguments[0].value = '{FOGO_ADDRESS}';", pubkey_input)
            
            logger.info(f"Attempt {attempt}: Selecting '{token_type}' radio button")
            # Map token type to label XPath
            radio_xpath = {
                "1_fogo_native": '//label[contains(.//span, "1 FOGO (native)")]/input',
                "1_fogo": '//label[contains(.//span, "1") and contains(.//span, "FOGO")]/input',
                "10_fusd": '//label[contains(.//span, "10") and contains(.//span, "fUSD")]/input'
            }.get(token_type)
            if not radio_xpath:
                raise ValueError(f"Invalid token type: {token_type}")
            
            # Click the label to select the radio button
            radio_label = wait.until(EC.element_to_be_clickable((By.XPATH, radio_xpath.replace('/input', ''))))
            logger.info(f"Attempt {attempt}: Radio label found for {token_type}: {radio_label.is_displayed()}")
            radio_input = radio_label.find_element(By.XPATH, './input')
            logger.info(f"Attempt {attempt}: Radio button enabled: {radio_input.is_enabled()}, selected: {radio_input.is_selected()}")
            if not radio_input.is_selected():
                logger.info(f"Attempt {attempt}: Clicking '{token_type}' radio label")
                try:
                    driver.execute_script("arguments[0].click();", radio_label)  # Use JavaScript click for phx-hook
                    wait.until(EC.element_to_be_selected(radio_input))
                except InvalidElementStateException:
                    logger.warning(f"Attempt {attempt}: Failed to click via JavaScript, retrying after delay")
                    time.sleep(retry_delay)
                    continue
                logger.info(f"Attempt {attempt}: Radio button {token_type} selected: {radio_input.is_selected()}")
            
            logger.info(f"Attempt {attempt}: Submitting form")
            submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Request Tokens")]')))
            logger.info(f"Attempt {attempt}: Submit button enabled: {submit_button.is_enabled()}, displayed: {submit_button.is_displayed()}")
            driver.execute_script("arguments[0].click();", submit_button)  # Use JavaScript click for phx-hook
            
            logger.info(f"Attempt {attempt}: Waiting for submission to process")
            time.sleep(20)  # Wait time for processing response
            
            logger.info(f"Attempt {attempt}: Checking for submission response")
            response_text = driver.find_element(By.TAG_NAME, "body").text
            logger.info(f"Attempt {attempt}: Faucet response: {response_text}")
            print(f"Attempt {attempt}: Faucet response: {response_text}")
            
            # Check for success or known errors
            if any(x in response_text for x in ["Sent 1 FOGO", "Sent 10 fUSD", "Success"]):
                print(f"Attempt {attempt}: Success: {token_type} tokens sent to your address!")
                return True
            elif any(x in response_text for x in ["High demand", "recently claimed", "Rate limit", "Couldn't execute transaction"]) or \
                 "Testnet Faucet" in response_text and "Request Tokens" in response_text and not any(x in response_text for x in ["Sent", "Success"]):
                print(f"Attempt {attempt}: Error: Faucet rate limit, high demand, or transaction failed for {token_type}. Waiting before retry...")
                return False
            else:
                logger.info(f"Attempt {attempt}: Full page source for unknown response: {driver.page_source}")
                print(f"Attempt {attempt}: Unknown response. Check bot.log for details.")
                return False
        
        except (InvalidElementStateException, TimeoutException) as e:
            logger.error(f"Attempt {attempt} (Retry {retry + 1}/{max_retries}): Failed due to {str(e)}")
            if retry < max_retries - 1:
                logger.info(f"Attempt {attempt}: Retrying after {retry_delay} seconds")
                time.sleep(retry_delay)
                continue
            logger.error(f"Attempt {attempt}: Max retries reached")
            print(f"Attempt {attempt}: Error during claim: {str(e)}")
            return False

def main():
    driver = None
    try:
        while True:
            try:
                num_loops = int(input("Enter the number of claim attempts (1 or more): "))
                if num_loops < 1:
                    print("Please enter a number >= 1.")
                    continue
                break
            except ValueError:
                print("Invalid input. Please enter a valid number.")
        
        while True:
            token_type = input("Enter token type to claim (1_fogo_native, 1_fogo, or 10_fusd): ").strip().lower()
            if token_type in ["1_fogo_native", "1_fogo", "10_fusd"]:
                break
            print("Invalid token type. Please enter '1_fogo_native', '1_fogo', or '10_fusd'.")
        
        logger.info(f"Starting bot with {num_loops} claim attempts for {token_type}")
        
        logger.info("Initializing Chrome driver")
        driver = uc.Chrome(
            options=options,
            driver_executable_path="/usr/local/bin/chromedriver",
            version_main=138
        )
        logger.info(f"ChromeDriver version: {driver.capabilities['chrome']['chromedriverVersion']}")
        
        logger.info(f"Navigating to {FAUCET_URL}")
        driver.get(FAUCET_URL)
        print("Browser opened in headless mode. If Cloudflare verification is required, you may need to run with xvfb or a GUI.")
        input("Press Enter after page load (or if verification is bypassed)...")
        
        wait = WebDriverWait(driver, 120)  # Increased timeout for Cloudflare
        for attempt in range(1, num_loops + 1):
            success = perform_faucet_claim(driver, wait, token_type, attempt)
            if attempt < num_loops:  # Don't wait after the last attempt
                wait_time = 15 if not success else 7  # 1 hour for failures, 15 seconds for success
                logger.info(f"Waiting {wait_time} seconds before attempt {attempt + 1}/{num_loops}")
                time.sleep(wait_time)
            
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
        print(f"Error: {str(e)}")
        
    finally:
        logger.info("Closing browser")
        if driver is not None:
            driver.quit()
        else:
            logger.warning("Driver was not initialized, skipping quit")

if __name__ == "__main__":
    main()
