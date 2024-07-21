from flask import Flask, request, render_template, send_file, url_for, jsonify
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import io
import re

app = Flask(__name__)

def scrape_flipkart_search(FSN_list):
    global progress
    progress = 0
    all_data = []

    total_fsns = len(FSN_list)
    for idx, FSN in enumerate(FSN_list):
        if total_fsns == 0:
            progress = 0
        else:
            progress = int((idx + 0.5) / total_fsns * 100)

        print(f"Processing FSN: {FSN}")
        print(f"Progress: {progress}")
        url = f"https://www.flipkart.com/product/p/itme?pid={FSN}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()  # Check if the request was successful
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            title_element = soup.find('span', class_='KalC6f')
            title = title_element.text.strip() if title_element else 'N/A'

            price_element = soup.find('div', class_='Nx9bqj CxhGGd')
            price = price_element.text.strip() if price_element else 'N/A'

            sold_out_element = soup.find('div', class_='Z8JjpR')
            sold_out = sold_out_element.text.strip() if sold_out_element else 'Available'

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

            seller_element = soup.find('div', id='sellerName')
            seller_name = seller_element.text.strip() if seller_element else 'N/A'

            all_data.append({
                'FSN': FSN,
                'TITLE': title,
                'Price': price,
                'Ratings': rating,
                'Rating Count': rating_count,
                'Review Count': review_count,
                'SOLD OUT': sold_out,
                'SELLER NAME': seller_name
            })
        except Exception as e:
            print(f"Error occurred for FSN: {FSN}. Error: {e}")
            continue

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
    df = scrape_flipkart_search(FSN_list)
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
