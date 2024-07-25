from flask import Flask, request, render_template, send_file, url_for, jsonify
import pandas as pd
import io
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
import time
import random

app = Flask(__name__)
progress = 0
progress2 = 0

user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    # Add more user agents here
]

async def fetch(session, url):
    headers = {
        'User-Agent': random.choice(user_agents),
    }
    async with session.get(url, headers=headers) as response:
        return await response.text()

def convert_to_int(value):
    try:
        if isinstance(value, int):
            return value
        elif isinstance(value, str):
            cleaned_value = value.replace(',', '').strip()
            return int(cleaned_value)
        else:
            raise ValueError(f"Unsupported type: {type(value)}")
    except ValueError as e:
        print(f"Failed to convert value: {value}. Error: {e}")
        return 0

async def extract_star_ratings(soup):
    star_ratings = {'5_star': '0', '4_star': '0', '3_star': '0', '2_star': '0', '1_star': '0'}
    try:
        div_elements = soup.find_all('div', class_='BArk-j')
        for i, div in enumerate(div_elements[:5]):  # Limit to first 5 for star ratings
            rating_text = div.get_text(strip=True)
            rating_value = convert_to_int(rating_text)
            if i == 0:
                star_ratings['5_star'] = rating_value
            elif i == 1:
                star_ratings['4_star'] = rating_value
            elif i == 2:
                star_ratings['3_star'] = rating_value
            elif i == 3:
                star_ratings['2_star'] = rating_value
            elif i == 4:
                star_ratings['1_star'] = rating_value
    except Exception as e:
        print(f"Error extracting star ratings: {e}")
    return star_ratings

async def extract_parameter_ratings(soup):
    parameters = {}
    parameter_elements = soup.select('div._5nb2hu')
    for i, param in enumerate(parameter_elements, 1):
        parameter_name_element = param.find('div', class_='NTiEl0')
        parameter_rating_element = param.find('text', class_='_2DdnFS')
        
        parameter_name = parameter_name_element.text.strip() if parameter_name_element else f'Parameter{i} Name'
        parameter_rating = parameter_rating_element.text.strip() if parameter_rating_element else 0
        
        parameters[f'Parameter{i} Name'] = parameter_name
        parameters[f'Parameter{i} Rating'] = parameter_rating
    return parameters

async def scrape_flipkart_search(FSN_list):
    global progress
    progress = 0
    all_data = []
    total_fsns = len(FSN_list)

    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, f"https://www.flipkart.com/product/p/itme?pid={FSN}") for FSN in FSN_list]
        responses = await asyncio.gather(*tasks)

        for idx, html in enumerate(responses):
            progress = int((idx + 1) / total_fsns * 100)
            print(f"Processing FSN: {FSN_list[idx]}")
            print(f"Progress: {progress}")

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

            parameter_ratings = await extract_parameter_ratings(soup)
            star_ratings = await extract_star_ratings(soup)

            all_data.append({
                'FSN': FSN_list[idx],
                'TITLE': title,
                'Price': price,
                'Ratings': rating,
                'Rating Count': rating_count,
                'Review Count': review_count,
                'SOLD OUT': sold_out,
                'SELLER NAME': seller_name,
                '5 Star Ratings': star_ratings.get('5_star', '0'),
                '4 Star Ratings': star_ratings.get('4_star', '0'),
                '3 Star Ratings': star_ratings.get('3_star', '0'),
                '2 Star Ratings': star_ratings.get('2_star', '0'),
                '1 Star Ratings': star_ratings.get('1_star', '0'),
                **parameter_ratings
            })

    df = pd.DataFrame(all_data)
    return df

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
async def scrape():
    asins = request.form['asins']
    FSN_list = asins.split()

    start_time = time.time()
    df = await scrape_flipkart_search(FSN_list)
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
async def price_comparison():
    start_time = time.time()
    file = request.files.get('file')
    df = pd.read_excel(file, header=0)
    df.columns = ['FSN', 'Desired Price']
    FSN_list = df['FSN'].tolist()
    desired_prices = dict(zip(df['FSN'], df['Desired Price']))
    results = []

    global progress2
    progress2 = 0
    total_fsnss = len(FSN_list)

    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, f"https://www.flipkart.com/product/p/itme?pid={fsn}") for fsn in FSN_list]
        responses = await asyncio.gather(*tasks)

        for idxx, html in enumerate(responses):
            progress2 = int((idxx + 1) / total_fsnss * 100)
            update_progress2(progress2)

            soup = BeautifulSoup(html, 'html.parser')

            price, status, title = await scrape_price(soup)

            if price is not None:
                try:
                    price_value = float(re.sub('[^\d.]', '', price))
                    desired_price = desired_prices.get(FSN_list[idxx])
                    if desired_price:
                        diff = price_value - desired_price
                        result = f"FSN: {FSN_list[idxx]}, Title: {title}, Price: {price}, Difference: {diff:.2f}"
                        results.append(result)
                except ValueError:
                    results.append(f"FSN: {FSN_list[idxx]}, Price parsing error")

    end_time = time.time()
    run_time = end_time - start_time

    results_file = io.BytesIO()
    with open('Price_Comparison_Results.txt', 'w') as file:
        for result in results:
            file.write(result + '\n')
        file.seek(0)

    with open('Price_Comparison_Results.txt', 'wb') as file:
        file.write(results_file.getbuffer())

    return render_template('index.html', run_time=run_time, download_link=url_for('download_file_comparison'))

@app.route('/download_comparison')
def download_file_comparison():
    return send_file(
        'Price_Comparison_Results.txt',
        mimetype='text/plain',
        as_attachment=True,
        download_name='Price_Comparison_Results.txt'
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
