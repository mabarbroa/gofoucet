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

FAUCET_URL = "https://faucet.fogo.io"

# Configure Chrome options
logger.info("Configuring Chrome options")
options = uc.ChromeOptions()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--window-size=1920,1080")
options.add_argument("--headless=new")
options.binary_location = "/opt/google/chrome/google-chrome"

def read_addresses(filename="address.txt"):
    try:
        with open(filename, "r") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"Gagal membaca file address.txt: {e}")
        return []

def perform_faucet_claim(driver, wait, token_type, attempt, address):
    max_retries = 3
    retry_delay = 5

    for retry in range(max_retries):
        try:
            logger.info(f"[{address}] Attempt {attempt} (Retry {retry + 1}/{max_retries})")
            time.sleep(5)

            pubkey_input = wait.until(EC.element_to_be_clickable((By.NAME, "pubkey")))
            logger.info(f"[{address}] Input pubkey found")

            try:
                pubkey_input.clear()
                pubkey_input.send_keys(address)
            except InvalidElementStateException:
                logger.warning(f"[{address}] Fallback to JS input")
                driver.execute_script("arguments[0].value = '';", pubkey_input)
                driver.execute_script(f"arguments[0].value = '{address}';", pubkey_input)

            radio_xpath = {
                "1_fogo_native": '//label[contains(.//span, "1 FOGO (native)")]/input',
                "1_fogo": '//label[contains(.//span, "1") and contains(.//span, "FOGO")]/input',
                "10_fusd": '//label[contains(.//span, "10") and contains(.//span, "fUSD")]/input'
            }.get(token_type)
            if not radio_xpath:
                raise ValueError(f"Invalid token type: {token_type}")

            radio_label = wait.until(EC.element_to_be_clickable((By.XPATH, radio_xpath.replace('/input', ''))))
            radio_input = radio_label.find_element(By.XPATH, './input')
            if not radio_input.is_selected():
                driver.execute_script("arguments[0].click();", radio_label)
                wait.until(EC.element_to_be_selected(radio_input))

            submit_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(text(), "Request Tokens")]')))
            driver.execute_script("arguments[0].click();", submit_button)

            time.sleep(20)
            response_text = driver.find_element(By.TAG_NAME, "body").text
            logger.info(f"[{address}] Faucet response: {response_text}")

            if any(x in response_text for x in ["Sent 1 FOGO", "Sent 10 fUSD", "Success"]):
                print(f"[{address}] Attempt {attempt}: SUCCESS")
                return True
            elif any(x in response_text for x in ["High demand", "recently claimed", "Rate limit", "Couldn't execute transaction"]):
                print(f"[{address}] Attempt {attempt}: RATE LIMITED or ERROR")
                return False
            else:
                print(f"[{address}] Attempt {attempt}: UNKNOWN RESPONSE")
                return False

        except (InvalidElementStateException, TimeoutException) as e:
            logger.error(f"[{address}] Retry {retry + 1}: Error: {e}")
            if retry < max_retries - 1:
                time.sleep(retry_delay)
                continue
            return False

def main():
    addresses = read_addresses()
    if not addresses:
        print("Tidak ada address ditemukan di address.txt")
        return

    while True:
        try:
            num_loops = int(input("Berapa kali klaim per address?: "))
            if num_loops < 1:
                print("Minimal 1")
                continue
            break
        except ValueError:
            print("Masukkan angka yang valid")

    while True:
        token_type = input("Jenis token (1_fogo_native, 1_fogo, 10_fusd): ").strip().lower()
        if token_type in ["1_fogo_native", "1_fogo", "10_fusd"]:
            break
        print("Input tidak valid.")

    for idx, address in enumerate(addresses, 1):
        logger.info(f"[{address}] Starting claim for address {idx}/{len(addresses)}")

        try:
            driver = uc.Chrome(
                options=options,
                driver_executable_path="/usr/local/bin/chromedriver",
                version_main=138
            )
            driver.get(FAUCET_URL)
            input("Tekan Enter jika sudah melewati Cloudflare...")

            wait = WebDriverWait(driver, 120)
            for attempt in range(1, num_loops + 1):
                success = perform_faucet_claim(driver, wait, token_type, attempt, address)
                if attempt < num_loops:
                    delay = 15 if not success else 7
                    time.sleep(delay)

        except Exception as e:
            logger.error(f"[{address}] Error utama: {e}")
        finally:
            driver.quit()

        logger.info(f"[{address}] Selesai. Menunggu 10 detik sebelum address berikutnya.")
        time.sleep(10)

if __name__ == "__main__":
    main()

