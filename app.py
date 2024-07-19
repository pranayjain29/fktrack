from flask import Flask, request, render_template, send_file, url_for
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import pandas as pd
import time
import io
import re

app = Flask(__name__)

def scrape_blinkit_search(FSN_list):
    all_data = []
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration
    chrome_options.add_argument("--no-sandbox")  # Bypass OS security model

    # Initialize the WebDriver once
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

    for FSN in FSN_list:
        print(f"Processing FSN: {FSN}")

        url = f"https://www.flipkart.com/product/p/itme?pid={FSN}"
        driver.get(url)
        time.sleep(0.5)  # Reduced delay to allow the page to load

        # Get page source after JavaScript has loaded
        html = driver.page_source

        # Parse the HTML with BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        try:
            # TITLE
            title_element = soup.find('div', class_='KalC6f').find('p')
            title = title_element.text.strip() if title_element else 'N/A'
            
            # PRICE
            element = soup.find(class_="Nx9bqj CxhGGd")
            price = element.text.strip()[1:] if element else None  # Remove the currency symbol if price exists

            # SOLD OUT
            element = soup.find(class_="Z8JjpR")
            sold_out = element.text.strip() if element else None

            # Extract rating
            rating_element = soup.find('div', class_='XQDdHH')
            rating = rating_element.text.strip() if rating_element else 'N/A'
            
            # Extract reviews
            review_element = soup.find('span', class_='Wphh3N')
            review = review_element.text.strip() if review_element else 'N/A'
            
            # Using regex to extract numeric values for rating count and review count
            rating_count = 'N/A'
            review_count = 'N/A'
            
            match = re.search(r'(\d{1,3}(?:,\d{3})*|\d+)\s*Ratings\s*&\s*(\d{1,3}(?:,\d{3})*|\d+)\s*Reviews', review)
            if match:
                rating_count = int(match.group(1).replace(',', ''))
                review_count = int(match.group(2).replace(',', ''))
            
            # Converting extracted values to integers if they are numeric, otherwise keeping them as 'N/A'
            rating_count = int(rating_count) if rating_count != 'N/A' else 'N/A'
            review_count = int(review_count) if review_count != 'N/A' else 'N/A'

            # SELLER NAME
            seller_element = soup.find(id="sellerName")
            seller_name = seller_element.text.strip() if seller_element else None

            all_data.append({'FSN': FSN, 'TITLE': title, 'Price': price, 'Ratings': rating, 
                             'Rating Count': rating_count, 'Review Count': review_count, 'SOLD OUT': sold_out, 
                             'SELLER NAME': seller_name})
        except Exception as e:
            print(f"Error occurred for FSN: {FSN}. Error: {e}")
            continue

    # Quit the driver after processing all FSNs
    driver.quit()

    # Create a DataFrame from the dictionary
    df = pd.DataFrame(all_data)
    return df

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape():
    asins = request.form['asins']
    FSN_list = asins.split()
    
    # Measure the runtime of the scraping function
    start_time = time.time()
    df = scrape_blinkit_search(FSN_list)
    end_time = time.time()
    run_time = end_time - start_time

    # Save DataFrame to Excel file in memory
    excel_file = io.BytesIO()
    df.to_excel(excel_file, index=False, sheet_name='Flipkart Prices')
    excel_file.seek(0)

    # Save the Excel file to a temporary file
    temp_file_path = 'Flipkart_Price_scrapper.xlsx'
    with open(temp_file_path, 'wb') as f:
        f.write(excel_file.getbuffer())

    return render_template('index.html', run_time=run_time, download_link=url_for('download_file'))

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
