from flask import Flask, request, render_template, send_file, url_for, jsonify
import pandas as pd
import io
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
import time
import random
import urllib.parse
import logging

app = Flask(__name__)
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:91.0) Gecko/20100101 Firefox/91.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
]

mobile_user_agents = ['Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.93 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 13_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 9; SM-A505F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.1.2 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 8.0.0; Pixel 2 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.87 Mobile Safari/537.36']
def get_headers():
    return {
        'User-Agent': random.choice(user_agents),
    }

def get_mobile_headers():
    return {
        'User-Agent': random.choice(mobile_user_agents),
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive'
    }

def extract_pid(url):
    try:
        return url.split('pid=')[-1].split('&')[0]
    except IndexError:
        return None

async def fetch(session, url):
    headers = {
        'User-Agent': random.choice(user_agents),
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive'
    }
    
    async with session.get(url, headers=headers) as response:
            return await response.text()
    
async def fetch_mob(session, url):
    headers = get_mobile_headers()
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


@app.route('/download')
def download_file():
    return send_file(
        'Flipkart_Price_scrapper.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='Flipkart_Price_scrapper.xlsx'
    )

async def scrape_flipkart_product2(pid_list, sponsored_list, page_list, rank_list):
    all_data = []
    global progress
    progress = 0

    async with aiohttp.ClientSession() as session:
        tasks = [fetch(session, f"https://www.flipkart.com/product/p/itme?pid={pid}") for pid in pid_list]
        html_responses = await asyncio.gather(*tasks)

        tasks_mob = [fetch_mob(session, f"https://www.flipkart.com/product/p/itme?pid={pid}") for pid in pid_list]
        html_mob_responses = await asyncio.gather(*tasks_mob)

        total_fsns = len(pid_list)
        for i, pid in enumerate(pid_list):
            progress = int((i + 1) / total_fsns * 100)
            print(f"Processing FSN: {pid_list[i]}")
            print(f"Progress: {progress}")

            html = html_responses[i]
            soup = BeautifulSoup(html, 'html.parser')

            html_mob = html_mob_responses[i]
            soup_mob = BeautifulSoup(html_mob, 'html.parser') if html_mob else None

            effective_price = None
            if soup_mob:
                html_content = soup_mob.prettify()
                price_pattern = r'([\w\s]*?)\s*₹(\d{1,3}(?:,\d{3})*|\d+)'
                matches = re.findall(price_pattern, html_content)
                for preceding_text, price in matches:
                    if not preceding_text.strip():
                        effective_price = float(price.replace(',', ''))

            first_number = second_number = 0
            if soup_mob:
                div_mob = soup_mob.find('div', class_='r-rjixqe')
                if div_mob:
                    text_content = ' '.join(span.get_text() for span in div_mob.find_all('span'))
                    numbers = re.findall(r'\d{1,3}(?:,\d{3})*|\d+', text_content)
                    if numbers:
                        first_number = numbers[0].replace(',', '')
                        second_number = numbers[1]

            div = soup.find('div', class_='KalC6f')
            title = div.find('p').text.strip() if div and div.find('p') else "Not found"

            brand = title.split()[0]

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

            product_data = {
                'Orders': first_number,
                'Days': second_number,
                'PID': pid,
                'Sponsored': sponsored_list[i],
                'Title': title,
                'Brand': brand,
                'Price': price,
                'Effective Price': effective_price,
                'Rating': rating,
                'Rating Count': rating_count,
                'Review Count': review_count,
                'Sold Out': sold_out,
                'Seller Name': seller_name,
                'Page': page_list[i],
                'Rank': rank_list[i],
                '5 Star Ratings': star_ratings.get('5_star', '0'),
                '4 Star Ratings': star_ratings.get('4_star', '0'),
                '3 Star Ratings': star_ratings.get('3_star', '0'),
                '2 Star Ratings': star_ratings.get('2_star', '0'),
                '1 Star Ratings': star_ratings.get('1_star', '0'),
                **parameter_ratings
            }

            all_data.append(product_data)

    return all_data

async def scrape_pids(query, pages):
    base_url = "https://www.flipkart.com/search"
    pids = []
    sponsored_status = []
    paging = []
    rank = []
    counter=0

    async with aiohttp.ClientSession() as session:
        # Create a list of tasks for fetching all pages concurrently
        tasks = [fetch(session, f"{base_url}?q={urllib.parse.quote(query)}&page={page}") for page in range(1, pages + 1)]
        responses = await asyncio.gather(*tasks)
        total_pages = len(responses)

        for idx, html in enumerate(responses):
            if html is None:
                logging.info(f"Skipping page: {idx + 1} due to fetch error.")
                continue
            progress = int((idx + 1) / total_pages * 100)
            logging.info(f"Processing page: {idx + 1}/{total_pages}")
            logging.info(f"Progress: {progress}%")

            soup = BeautifulSoup(html, 'html.parser')

            # Find all product links
            product_elements = soup.find_all('a', class_='CGtC98')
            product_urls = ["https://www.flipkart.com" + elem['href'] for elem in product_elements if 'href' in elem.attrs]

            if (not product_urls):
                print("Wrong layout")
                return [],[],[],[]
            
            for elem in product_elements:
                pid = extract_pid(elem['href'])
                if pid:
                    counter += 1
                    pids.append(pid)
                    is_sponsored = 'Yes' if elem.find('div', class_='f8qK5m') else 'No'
                    sponsored_status.append(is_sponsored)   
                    paging.append(idx+1)
                    rank.append(counter)
    
    return pids, sponsored_status, paging, rank

async def scrape_pids2(query, pages):
    base_url = "https://www.flipkart.com/search"
    pids = []
    sponsored_status = []
    paging = []
    rank = []
    counter=0

    async with aiohttp.ClientSession() as session:
        # Create a list of tasks for fetching all pages concurrently
        tasks = [fetch(session, f"{base_url}?q={urllib.parse.quote(query)}&page={page}") for page in range(1, pages + 1)]
        responses = await asyncio.gather(*tasks)
        total_pages = len(responses)

        for idx, html in enumerate(responses):
            if html is None:
                print(f"Skipping page: {idx + 1} due to fetch error.")
                continue
            progress = int((idx + 1) / total_pages * 100)
            print(f"Processing page: {idx + 1}/{total_pages}")
            print(f"Progress: {progress}%")

            soup = BeautifulSoup(html, 'html.parser')

            # Find all product links
            product_elements = soup.find_all('div', attrs={'data-id': True})
            
            for elem in product_elements:
                pid = elem.get('data-id')
                if pid:
                    counter += 1
                    pids.append(pid)
                    # Check if the product is sponsored
                    is_sponsored = 'Yes' if elem.find('div', class_='xgS27m') else 'No'
                    sponsored_status.append(is_sponsored)
                    paging.append(idx+1)
                    rank.append(counter)
    
    return pids, sponsored_status, paging, rank

@app.route('/fetch_competitor_data', methods=['POST'])
async def comp_scrape():
    query = request.form['query']
    pages = int(request.form['num_pages'])
    all_data = []
    starttime = time.time()

    pids, sponsored_status, paging, rank = await scrape_pids(query, pages)
    if not pids:
        pids, sponsored_status, paging, rank = await scrape_pids2(query, pages)

    scrape_tasks = await scrape_flipkart_product2(pids, sponsored_status, paging, rank)
    all_data.extend(scrape_tasks)
    endtime = time.time()
    run_timee = endtime - starttime

    df = pd.DataFrame(all_data)
    print(df.shape)

    comp_excel_file = io.BytesIO()
    with pd.ExcelWriter(comp_excel_file, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Flipkart Comp Data')
    comp_excel_file.seek(0)

    temp_file_path = 'Flipkart_CompData_scrapper.xlsx'
    with open(temp_file_path, 'wb') as f:
        f.write(comp_excel_file.getvalue())

    return render_template('competitor_data.html', fetch_runtime=run_timee, fetch_download_link=url_for('download_file_comp'))

@app.route('/index2')
def index2():
    return render_template('competitor_data.html')

@app.route('/self')
def self():
    return render_template('index.html')

@app.route('/download_file_comp')
def download_file_comp():
    temp_file_path = 'Flipkart_CompData_scrapper.xlsx'
    return send_file(
        temp_file_path,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=temp_file_path
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
