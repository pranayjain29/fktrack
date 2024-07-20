from flask import Flask, request, render_template, send_file, url_for, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
import io
import re
import logging
import threading

app = Flask(__name__)

# Global variable to store progress
progress = 0

# Setup logging
logging.basicConfig(level=logging.INFO)

# Function to scrape a single FSN
def scrape_fsn(driver, FSN):
    url = f"https://www.flipkart.com/product/p/itme?pid={FSN}"
    driver.get(url)
    time.sleep(2)  # Adjust delay to allow the page to load

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')

    title_element = soup.find('div', class_='KalC6f').find('p')
    title = title_element.text.strip() if title_element else 'N/A'

    element = soup.find(class_="Nx9bqj CxhGGd")
    price = element.text.strip()[1:] if element else None

    element = soup.find(class_="Z8JjpR")
    sold_out = element.text.strip() if element else None

    rating_element = soup.find('div', class_='XQDdHH')
    rating = rating_element.text.strip() if rating_element else 'N/A'

    review_element = soup.find('span', class_='Wphh3N')
    review = review_element.text.strip() if review_element else 'N/A'

    rating_count = 0
    review_count = 0

    match = re.search(r'(\d{1,3}(?:,\d{3})*|\d+)\s*Ratings\s*&\s*(\d{1,3}(?:,\d{3})*|\d+)\s*Reviews', review)
    if match:
        rating_count = int(match.group(1).replace(',', ''))
        review_count = int(match.group(2).replace(',', ''))

    rating_count = int(rating_count) if rating_count != 'N/A' else 0
    review_count = int(review_count) if review_count != 'N/A' else 0

    seller_element = soup.find(id="sellerName")
    seller_name = seller_element.text.strip() if seller_element else None

    return {'FSN': FSN, 'TITLE': title, 'Price': price, 'Ratings': rating, 
            'Rating Count': rating_count, 'Review Count': review_count, 'SOLD OUT': sold_out, 
            'SELLER NAME': seller_name}

# Function to run the scraping for a part of the FSN list
def scrape_part(FSN_list_part, result_list, index):
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration
    chrome_options.add_argument("--no-sandbox")  # Bypass OS security model
    chrome_options.binary_location = "/usr/bin/google-chrome"  # Path to the Chrome binary in the Docker container

    try:
        driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)
    except Exception as e:
        logging.error(f"Error initializing WebDriver: {e}")
        return

    part_data = []
    for FSN in FSN_list_part:
        try:
            part_data.append(scrape_fsn(driver, FSN))
        except Exception as e:
            logging.error(f"Error occurred for FSN: {FSN}. Error: {e}")
    
    driver.quit()
    result_list[index] = part_data

def scrape_blinkit_search(FSN_list):
    global progress
    progress = 0
    all_data = []
    total_fsns = len(FSN_list)

    # Split FSN list into three parts
    FSN_parts = [FSN_list[i::3] for i in range(3)]
    
    result_list = [None] * 3
    threads = []

    # Start three threads to scrape data in parallel
    for i in range(3):
        thread = threading.Thread(target=scrape_part, args=(FSN_parts[i], result_list, i))
        threads.append(thread)
        thread.start()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    # Combine results from all threads
    for part_data in result_list:
        all_data.extend(part_data)

    df = pd.DataFrame(all_data)
    return df

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    global progress
    progress = 0
    asins = request.form['asins']
    FSN_list = asins.split()

    start_time = time.time()
    df = scrape_blinkit_search(FSN_list)
    end_time = time.time()
    run_time = end_time - start_time

    excel_file = io.BytesIO()
    df.to_excel(excel_file, index=False, sheet_name='Flipkart Prices')
    excel_file.seek(0)

    temp_file_path = 'Flipkart_Price_scrapper.xlsx'
    with open(temp_file_path, 'wb') as f:
        f.write(excel_file.getbuffer())

    return render_template('index.html', run_time=run_time, download_link=url_for('download_file'))

@app.route('/progress')
def progress_endpoint():
    return jsonify({'progress': progress})

@app.route('/download')
def download_file():
    return send_file(
        'Flipkart_Price_scrapper.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='Flipkart_Price_scrapper.xlsx'
    )

if __name__ == '__main__':
    app.run(debug=True, port=3000)
