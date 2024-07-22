from flask import Flask, request, render_template, send_file, url_for, jsonify
import pandas as pd
import io
import requests
from bs4 import BeautifulSoup
import re
import time

app = Flask(__name__)
progress = 0

def scrape_flipkart_search(FSN_list):
    global progress
    progress = 0
    update_progress(progress)
    all_data = []
    total_fsns = len(FSN_list)

    if total_fsns == 0:
            progress = 0

    for idx, FSN in enumerate(FSN_list):

        progress = int((idx + 1) / total_fsns * 100)

        update_progress(progress)
        print(f"Processing FSN: {FSN}")
        print(f"Progress: {progress}")
        url = f"https://www.flipkart.com/product/p/itme?pid={FSN}"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            div = soup.find('div', class_='KalC6f')
            title = div.find('p').text.strip() if div and div.find('p') else "Not found"

            price_element = soup.find('div', class_='Nx9bqj CxhGGd')
            price = price_element.text.strip() if price_element else 'N/A'

            sold_out_element = soup.find('div', class_='Z8JjpR')
            sold_out = sold_out_element.text.strip() if sold_out_element else 'Available'

            rating_element = soup.find('div', class_='XQDdHH')
            rating = rating_element.text.strip() if rating_element else 'N/A'

            review_element = soup.find('span', class_='Wphh3N')
            review = review_element.text.strip() if review_element else 'N/A'

            rating_count = review_count = 0
            match = re.search(r'(\d{1,3}(?:,\d{3})*|\d+)\s*Ratings\s*&\s*(\d{1,3}(?:,\d{3})*|\d+)\s*Reviews', review)
            if match:
                rating_count = int(match.group(1).replace(',', ''))
                review_count = int(match.group(2).replace(',', ''))

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

@app.route('/progress', methods=['GET'])
def get_progress():
    global progress
    if progress >= 100:
        progress = 0
    return jsonify({'progress': progress})

def update_progress(value):
    global progress
    progress = value

def update_progress2(value):
    global progress2
    progress2 = value

@app.route('/price_comparison_progress', methods=['GET'])
def get_price_comparison_progress():
    global progress2
    if progress2 >= 100:
        progress2 = 0
    return jsonify({'progress': progress2})

@app.route('/download')
def download_file():
    return send_file(
        'Flipkart_Price_scrapper.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='Flipkart_Price_scrapper.xlsx'
    )

@app.route('/price_comparison', methods=['POST'])
def price_comparison():
    start_time = time.time()  # Add this line to capture the start time
    file = request.files.get('file')
    df = pd.read_excel(file, header=0)
    df.columns = ['FSN', 'Desired Price']
    FSN_list = df['FSN'].tolist()
    desired_prices = dict(zip(df['FSN'], df['Desired Price']))
    results = []

    global progress2
    progress2 = 0
    total_fsnss = len(FSN_list)

    for idxx, fsn in enumerate(FSN_list):

        progress2 = int((idxx + 1) / total_fsnss * 100)
        update_progress2(progress2)
        price, status, title = scrape_price(fsn)

        if price is not None:
            try:
                price = float(price.replace('₹', '').replace(',', '').strip()) if price else None
                price_difference = price - desired_prices.get(fsn, 0)
                
            except ValueError:
                price = 0
                continue

            if price_difference != 0 or status == 'SOLD OUT':
                results.append({
                    'FSN': fsn,
                    'TITLE': title,
                    'Price': price,
                    'Desired Price': desired_prices.get(fsn, 0),
                    'Price Difference': price_difference,
                    'SOLD OUT': status
                })

    results_df = pd.DataFrame(results)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        results_df.to_excel(writer, index=False, sheet_name='Price Comparison')

    output.seek(0)

    temp_file_path = 'price_comparison.xlsx'
    with open(temp_file_path, 'wb') as f:
        f.write(output.getbuffer())

    comparison_run_time = time.time() - start_time  # Capture the comparison runtime

    return render_template('index.html', comparison_run_time=comparison_run_time, comparison_download_link=url_for('download_comparison'))

@app.route('/download_comparison')
def download_comparison():
    return send_file(
        'price_comparison.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='price_comparison.xlsx'
    )

def scrape_price(fsn):
    url = f"https://www.flipkart.com/product/p/itme?pid={fsn}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        div = soup.find('div', class_='KalC6f')
        title = div.find('p').text.strip() if div and div.find('p') else "Not found"
        
        price_element = soup.find('div', class_='Nx9bqj CxhGGd')
        price = price_element.text.strip() if price_element else 'N/A'

        sold_out_element = soup.find('div', class_='Z8JjpR')
        status = sold_out_element.text.strip() if sold_out_element else 'Available'

        return price, status, title

    except Exception as e:
        print(f"Error occurred while scraping price for FSN: {fsn}. Error: {e}")
        return None, 'Error'

if __name__ == '__main__':
    app.run(debug=True, port=3000)
