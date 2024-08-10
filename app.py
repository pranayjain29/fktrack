from flask import Flask, request, render_template, send_file, url_for, jsonify, send_file
import pandas as pd
import io
import aiohttp
import asyncio
from bs4 import BeautifulSoup
import re
import time
import random
import urllib.parse
from playwright.async_api import async_playwright
import logging
import matplotlib.pyplot as plt
import plotly.express as px
from flask_caching import Cache
import dash
from dash import dcc
from dash import html
from dash import Dash
from dash.dependencies import Input, Output
import zipfile

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
cache = Cache(config={'CACHE_TYPE': 'simple'})
cache.init_app(app)
dash_app = Dash(__name__, server=app, url_base_pathname='/dash/')
figures = {}

dash_app.layout = html.Div([
    dcc.Graph(id='example-graph')
])

user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:91.0) Gecko/20100101 Firefox/91.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
]

mobile_user_agents = ['Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1']


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

    try:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.text()
            else:
                content = await response.text()
                print(f"Failed to fetch {url}. Status code: {response.status}")
                return None
    except Exception as e:
        return None
    
async def fetch_mob(session, url):
    headers = get_mobile_headers()
    try:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.text()
            else:
                print(f"Failed to fetch {url}. Status code: {response.status}")
                return None
    except Exception as e:
        return None


async def fetch_page(url, context):
    page = await context.new_page()
    await page.goto(url)
    content = await page.content()
    await page.close()
    return content

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

def clean_price(price_text):
    # Remove ₹ symbol and commas, then convert to float
    cleaned_price = re.sub(r'[₹,]', '', price_text)
    try:
        price = float(cleaned_price)
    except ValueError:
        price = 'N/A'
    return price

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

    connector = aiohttp.TCPConnector(limit=30)  # Increase the number of connections
    async with aiohttp.ClientSession(connector=connector) as session:
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
            price = clean_price(price_element.text.strip()) if price_element else 0

            sold_out_element = soup.find('div', class_='Z8JjpR')
            sold_out = sold_out_element.text.strip() if sold_out_element else 'Available'

            rating_element = soup.find('div', class_='XQDdHH')
            rating = rating_element.text.strip() if rating_element else 'N/A'

            review_element = soup.find('span', class_='Wphh3N')
            review = review_element.text.strip() if review_element else 'N/A'

            rating_count = review_count = 0
            match = re.search(r'(\d{1,2}(?:,\d{2})*(?:,\d{3})*|\d+)\s*Ratings\s*&\s*(\d{1,2}(?:,\d{2})*(?:,\d{3})*|\d+)\s*Reviews', review)

            if match:
                rating_count = int(match.group(1).replace(',', ''))
                review_count = int(match.group(2).replace(',', ''))

            seller_element = soup.find('div', id='sellerName')
            seller_name = seller_element.text.strip() if seller_element else 'N/A'

            seller_rating = 0.0
            if seller_name != 'N/A' and any(char.isdigit() for char in seller_name):
                try:
                    seller_rating = float(''.join(filter(lambda x: x.isdigit() or x == '.', seller_name.split()[-1])))
                    seller_name = seller_name[:seller_name.rfind(str(seller_rating))]
                except ValueError:
                    pass

            parameter_ratings = await extract_parameter_ratings(soup)
            star_ratings = await extract_star_ratings(soup)

            all_data.append({
                'FSN': FSN_list[idx],
                'Title': title,
                'Price': price,
                'Ratings': rating,
                'Rating Count': rating_count,
                'Review Count': review_count,
                'Availability': sold_out,
                'Seller Name': seller_name,
                'Seller Rating' : seller_rating,
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
    
    start_time = time.time()
    asins = request.form['asins']
    FSN_list = asins.split()
    
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

    connector = aiohttp.TCPConnector(limit=30)  # Increase the number of connections
    async with aiohttp.ClientSession(connector=connector) as session:
        
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
            
            if html is None:
                print(f"Skipping PID {pid} due to fetch error.")
                continue
            soup = BeautifulSoup(html, 'html.parser')

            html_mob = html_mob_responses[i]
            if html_mob is None:
                print(f"Skipping MOB PID {pid} due to fetch error.")
                continue
            soup_mob = BeautifulSoup(html_mob, 'html.parser') if html_mob else None

            first_number = second_number = 0
            if soup_mob:
                div_mob = soup_mob.find('div', class_='r-rjixqe')
                if div_mob:
                    text_content = ' '.join(span.get_text() for span in div_mob.find_all('span'))
                    numbers = re.findall(r'\d{1,3}(?:,\d{3})*|\d+', text_content)
                    if numbers:
                        first_number = int(numbers[0].replace(',', ''))
                        second_number = int(numbers[1])

            div = soup.find('div', class_='KalC6f')
            title = div.find('p').text.strip() if div and div.find('p') else "Not found"

            brand = title.split()[0]

            price_element = soup.find('div', class_='Nx9bqj CxhGGd')
            price = clean_price(price_element.text.strip()) if price_element else 0

            sold_out_element = soup.find('div', class_='Z8JjpR')
            sold_out = sold_out_element.text.strip() if sold_out_element else 'Available'

            rating_element = soup.find('div', class_='XQDdHH')
            rating = rating_element.text.strip() if rating_element else 'N/A'

            review_element = soup.find('span', class_='Wphh3N')
            review = review_element.text.strip() if review_element else 'N/A'

            rating_count = review_count = 0
            match = re.search(r'(\d{1,2}(?:,\d{2})*(?:,\d{3})*|\d+)\s*Ratings\s*&\s*(\d{1,2}(?:,\d{2})*(?:,\d{3})*|\d+)\s*Reviews', review)
            if match:
                rating_count = int(match.group(1).replace(',', ''))
                review_count = int(match.group(2).replace(',', ''))

            seller_element = soup.find('div', id='sellerName')
            seller_name = seller_element.text.strip() if seller_element else 'N/A'

            seller_rating = 0.0
            if seller_name != 'N/A' and any(char.isdigit() for char in seller_name):
                try:
                    seller_rating = float(''.join(filter(lambda x: x.isdigit() or x == '.', seller_name.split()[-1])))
                    seller_name = seller_name[:seller_name.rfind(str(seller_rating))]
                except ValueError:
                    pass

            parameter_ratings = await extract_parameter_ratings(soup)
            star_ratings = await extract_star_ratings(soup)

            DRR = round(first_number / second_number) if second_number != 0 else 0
            Weekly_Revenue = round(DRR*7*price)

            product_data = {
                
                'FSN': pid,
                'Sponsored': sponsored_list[i],
                'Title': title,
                'Brand': brand,
                'Price': price,
                'DRR':DRR,
                'Approx_Weekly_Revenue': Weekly_Revenue,
                'Rating': rating,
                'Rating Count': rating_count,
                'Review Count': review_count,
                'Sold Out': sold_out,
                'Seller Name': seller_name,
                'Seller Rating': seller_rating,
                'Page': page_list[i],
                'Rank': rank_list[i],
                '5 Star Ratings': star_ratings.get('5_star', '0'),
                '4 Star Ratings': star_ratings.get('4_star', '0'),
                '3 Star Ratings': star_ratings.get('3_star', '0'),
                '2 Star Ratings': star_ratings.get('2_star', '0'),
                '1 Star Ratings': star_ratings.get('1_star', '0'),
                **parameter_ratings,
                'Orders': first_number,
                'Days': second_number,
            }

            all_data.append(product_data)

    return all_data


async def scrape_pids(query, pages, sort_option):
    base_url = "https://www.flipkart.com/search"
    pids = []
    sponsored_status = []
    paging = []
    rank = []

    async with async_playwright() as p:
        async def fetch_page_data(page_num, repeat = 0):
            counter = 0
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=random.choice(user_agents))
            url = f"{base_url}?q={urllib.parse.quote(query)}&page={page_num}&sort=sort_option"
            logging.info(f"Inside first url: {url}")
            html = await fetch_page(url, context)
            soup = BeautifulSoup(html, 'html.parser')

            product_elements = soup.find_all('a', class_='CGtC98')
            local_pids, local_sponsored_status, local_paging, local_rank = [], [], [], []

            for elem in product_elements:
                pid = extract_pid(elem['href'])
                counter += 1
                if pid:
                    local_pids.append(pid)
                    is_sponsored = 'Yes' if elem.find('div', class_='f8qK5m') else 'No'
                    local_sponsored_status.append(is_sponsored)
                    local_paging.append(page_num)
                    local_rank.append(counter)
                    
            await browser.close()
            if not local_pids and repeat<5:
                return await fetch_page_data(page_num, repeat+1)
            return local_pids, local_sponsored_status, local_paging, local_rank

        tasks = [fetch_page_data(page) for page in range(1, pages + 1)]
        results = await asyncio.gather(*tasks)

        for result in results:
            pids.extend(result[0])
            sponsored_status.extend(result[1])
            paging.extend(result[2])
            rank.extend(result[3])

        
        logging.info(f"Inside first pids: {pids}")
    return pids, sponsored_status, paging, rank

async def scrape_pids2(query, pages, sort_option):
    
    base_url = "https://www.flipkart.com/search"
    pids = []
    sponsored_status = []
    paging = []
    rank = []

    async with async_playwright() as p:
        async def fetch_page_data(page_num, repeat = 0):
            counter = 0
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=random.choice(user_agents))
            url = f"{base_url}?q={urllib.parse.quote(query)}&page={page_num}&sort=sort_option"
            html = await fetch_page(url, context)
            soup = BeautifulSoup(html, 'html.parser')

            product_elements = soup.find_all('div', attrs={'data-id': True})
            local_pids, local_sponsored_status, local_paging, local_rank = [], [], [], []

            for elem in product_elements:
                pid = elem.get('data-id')
                counter += 1
                if pid:
                    local_pids.append(pid)
                    is_sponsored = 'Yes' if elem.find('div', class_='xgS27m') else 'No'
                    local_sponsored_status.append(is_sponsored)
                    local_paging.append(page_num)
                    local_rank.append(counter)
                    
            logging.info(f"Inside second local pids: {local_pids}")
            await browser.close()
            if not local_pids and repeat<5:
                return await fetch_page_data(page_num, repeat+1)
            return local_pids, local_sponsored_status, local_paging, local_rank

        tasks = [fetch_page_data(page) for page in range(1, pages + 1)]
        results = await asyncio.gather(*tasks)

        for result in results:
            pids.extend(result[0])
            sponsored_status.extend(result[1])
            paging.extend(result[2])
            rank.extend(result[3])

        logging.info(f"Inside second pids: {pids}")

    return pids, sponsored_status, paging, rank


@app.route('/fetch_competitor_data', methods=['POST'])
async def comp_scrape():

    start_time = time.time()
    query = request.form['query']
    pages = int(request.form['num_pages'])
    sort_option = request.form['sort_option']
    logging.info(sort_option)
    all_data = []
    repeat = 0

    pids, sponsored_status, paging, rank = await scrape_pids(query, pages, sort_option)
    if not pids:
        pids, sponsored_status, paging, rank = await scrape_pids2(query, pages, sort_option)
    
    logging.info(f"GOT PID, RANK: {pids}, {rank}")

    # Call a function to scrape product details using pids
    scrape_tasks = await scrape_flipkart_product2(pids, sponsored_status, paging, rank)
    all_data.extend(scrape_tasks)
    endtime = time.time()
    run_timee = endtime - start_time

    df = pd.DataFrame(all_data)
    print(df.shape)

    comp_excel_file = io.BytesIO()
    with pd.ExcelWriter(comp_excel_file, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Flipkart Comp Data')
    comp_excel_file.seek(0)

    temp_file_path = 'Flipkart_CompData_scrapper.xlsx'
    with open(temp_file_path, 'wb') as f:
        f.write(comp_excel_file.getvalue())

    df.to_csv('flipkart_comp_data.csv', index=False)
    return render_template('competitor_data.html', fetch_runtime=run_timee, fetch_download_link=url_for('download_file_comp'), analysis_link=url_for('analysis'))

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

@app.route('/price_comparison', methods=['POST'])
async def price_comparison():
    start_time = time.time()
    file = request.files.get('file')
    df = pd.read_excel(file, header=0)
    df.columns = ['FSN', 'Desired Price']
    FSN_list = df['FSN'].tolist()
    desired_prices = dict(zip(df['FSN'], df['Desired Price']))
    logging.info(df)
    logging.info(FSN_list)
    
    results = []

    df = await scrape_flipkart_search(FSN_list)
    for idxx, row in df.iterrows():
        price = row['Price']
        status = row['Availability']
        title = row['Title']
        desired_price = float(desired_prices.get(FSN_list[idxx]))

        if price is not None:
            try:
                price_value = float(price)
                desired_price = desired_prices.get(FSN_list[idxx])
                diff = price_value - desired_price

                if diff != 0 or status.lower() != 'available':
                    result = {
                        'FSN': FSN_list[idxx],
                        'Title': title,
                        'Price': price_value,
                        'Desired Price':desired_price,
                        'Availability': status,
                        'Difference': diff
                    }
                    results.append(result)
            except ValueError:
                results.append(f"FSN: {FSN_list[idxx]}, Price parsing error")

    df = pd.DataFrame(results)
    end_time = time.time()
    run_time = end_time - start_time

    results_file = io.BytesIO()
    with pd.ExcelWriter(results_file, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Flipkart Comparison Data')
    results_file.seek(0)

    temp_file_path = 'Flipkart_Comparison_Data.xlsx'
    with open(temp_file_path, 'wb') as f:
        f.write(results_file.getvalue())

    df.to_csv('flipkart_comp_data.csv', index=False)
    return render_template('index.html', run_time=run_time, download_link=url_for('download_file_comparison'))

@app.route('/download_comparison')
def download_file_comparison():
    return send_file(
        'Flipkart_Comparison_Data.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='Flipkart_Comparison_Data.xlsx'
    )

def calculate_counts(df, column_name):
        counts = df[column_name].value_counts().reset_index()
        counts.columns = [column_name, 'count']
        counts['Percentage'] = (counts['count'] / counts['count'].sum() * 100).round(1).astype(str) + '%'
        return counts

def calculate_metric(df, column_name, revenue_column):
    revenue = df.groupby(column_name)[revenue_column].sum().reset_index()
    revenue = revenue.sort_values(by=revenue_column, ascending=False)
    revenue['Percentage'] = (revenue[revenue_column] / revenue[revenue_column].sum() * 100).round(1).astype(str) + '%'
    return revenue

def create_bar_chart(df, x_column, y_column, text_column, title):
    fig = px.bar(
        df,
        x=x_column,
        y=y_column,
        text=text_column,
        labels={x_column: x_column, y_column: y_column},
        title=title,
    )
    fig.update_layout(
        font=dict(family='Montserrat, sans-serif', size=12),
        xaxis_title=None,
        yaxis_title=None,
        xaxis_tickangle=0,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    fig.update_traces(texttemplate='%{text}', textposition='outside')
    return fig

def generate_html(fig):
    return fig.to_html(full_html=False, include_plotlyjs='cdn')

def calculate_search_rank(df, page_column, rank_column):
    df['search_rank'] = (df[page_column] - 1) * df[rank_column].max() + df[rank_column]
    avg_search_rank = df.groupby('Brand')['search_rank'].mean().reset_index()
    avg_search_rank['search_rank'] = (avg_search_rank['search_rank'] / avg_search_rank['search_rank'].max() * 100).round(1)
    avg_search_rank = avg_search_rank.sort_values(by='search_rank', ascending=False).reset_index(drop=True)
    return avg_search_rank

def create_horizontal_bar_chart(df, x_column, y_column, title):
    print(df)
    # No need to sort here, use the sorted DataFrame as it is
    fig = px.bar(
        df,  # Use the sorted DataFrame
        x=x_column,
        y=y_column,
        orientation='h',
        labels={x_column: x_column, y_column: y_column},
        title=title,
    )
    
    # Set x-axis range from 0 to 100
    fig.update_layout(
        font=dict(family='Montserrat, sans-serif', size=12),
        xaxis_title=None,
        yaxis_title=None,
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis=dict(range=[0, 100])  # Set x-axis range from 0 to 100
    )
    
    fig.update_traces(
        texttemplate='%{x:.1f}%',  # Add percentage symbol to the labels
        textposition='outside'
    )
    
    return fig

def calculate_brand_percentage_by_page(df, page_column):
    brand_percentage_by_page = (
        df.groupby(['Brand', page_column])
        .size()
        .reset_index(name='count')
    )
    brand_percentage_by_page['Percentage'] = (
        brand_percentage_by_page['count'] / brand_percentage_by_page.groupby(page_column)['count'].transform('sum') * 100
    ).round(1).astype(str) + '%'
    return brand_percentage_by_page

def create_dash_layout(df):
    unique_pages = sorted(df['Page'].unique())
    
    dash_app.layout = html.Div([
        dcc.Dropdown(
            id='page-dropdown',
            options=[{'label': f'Page {i}', 'value': i} for i in unique_pages],
            value=1,  # Default value
            clearable=False
        ),
        dcc.Graph(id='bar-chart')
    ])
    
    @dash_app.callback(
        Output('bar-chart', 'figure'),
        Input('page-dropdown', 'value')
    )
    def update_chart(selected_page):
        filtered_df = df[df['Page'] == selected_page]
        brand_counts = filtered_df['Brand'].value_counts().reset_index()
        brand_counts.columns = ['Brand', 'count']
        brand_counts['Percentage'] = (brand_counts['count'] / brand_counts['count'].sum() * 100).round(1).astype(str) + '%'
        
        # Sort the DataFrame in descending order by 'count'
        brand_counts = brand_counts.sort_values(by='count', ascending=False)
        
        # Create the bar chart with explicitly sorted y-axis
        fig = px.bar(
            brand_counts,
            x='count',
            y='Brand',
            orientation='h',
            text='Percentage',
            labels={'count': 'Count', 'Brand': 'Brand'},
            title=f'Brand Distribution - Page {selected_page}'
        )
        
        # Update layout to ensure y-axis is sorted correctly
        fig.update_layout(
            yaxis=dict(categoryorder='total ascending'),
            font=dict(family='Montserrat, sans-serif', size=12),
            xaxis_title=None,
            yaxis_title=None,
            margin=dict(l=0, r=0, t=40, b=0)
        )
        fig.update_traces(texttemplate='%{text}', textposition='outside')

        global figures
        figures['rank_by_page'] = fig
        
        return fig
    
def create_charts(df):
    global figures
    brand_counts = calculate_counts(df, 'Brand')
    revenue_by_brand = calculate_metric(df, 'Brand', 'Approx_Weekly_Revenue')
    drr_by_brand = calculate_metric(df, 'Brand', 'DRR')
    avg_search_rank = calculate_search_rank(df, 'Page', 'Rank')

    fig1 = create_bar_chart(brand_counts, 'Brand', 'count', 'Percentage', 'Brand Distribution')
    fig2 = create_bar_chart(revenue_by_brand, 'Brand', 'Approx_Weekly_Revenue', 'Percentage', 'Weekly Revenue by Brand')
    fig3 = create_bar_chart(drr_by_brand, 'Brand', 'DRR', 'Percentage', 'DRR by Brand')
    fig_search_rank = create_horizontal_bar_chart(avg_search_rank, 'search_rank', 'Brand', 'Average Search Rank by Brand')

    figures['brand_distribution'] = fig1
    figures['weekly_revenue_by_brand'] = fig2
    figures['drr_by_brand'] = fig3
    figures['average_search_rank_by_brand'] = fig_search_rank

    return fig1, fig2, fig3, fig_search_rank
    

@app.route('/analysis')
def analysis():
    global figures
    # Read the DataFrame from the CSV file
    df = pd.read_csv('flipkart_comp_data.csv')
    df = df[df['Sponsored']=='No']
    df.loc[df['Seller Rating'] <= 2.0, 'Approx_Weekly_Revenue'] *= 0.5

    df = df.drop_duplicates(subset='FSN', keep='first')
    create_dash_layout(df)

    fig1, fig2, fig3, fig_search_rank = create_charts(df)
    

    # Generate HTML for the plots
    graph_html1 = generate_html(fig1)
    graph_html2 = generate_html(fig2)
    graph_html3 = generate_html(fig3)
    graph_html4 = generate_html(fig_search_rank)

    send_file(buffer, as_attachment=True, download_name='graphs.zip', mimetype='application/zip')

    return render_template('analysis.html', graph_html1=graph_html1, graph_html2=graph_html2,graph_html3=graph_html3,graph_html4=graph_html4
                           ,fetch_download_link=url_for('download_file_comp'), download_graphs=url_for('download_graphs'))

@app.route('/download_graphs')
def download_graphs():
   
    global figures
    logging.info(figures)
    buffer = io.BytesIO()
    
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        # List of figures to save
        figs = [
            ('brand_distribution.png', figures['brand_distribution']),
            ('weekly_revenue_by_brand.png', figures['weekly_revenue_by_brand']),
            ('drr_by_brand.png', figures['drr_by_brand']),
            ('average_search_rank_by_brand.png', figures['average_search_rank_by_brand']),
            ('rank_by_page.png', figures['rank_by_page'])
        ]
        
        # Save each figure as an image and add to the ZIP file
        for filename, fig in figs:
            img_buf = io.BytesIO()
            fig.write_image(img_buf, format='png')
            img_buf.seek(0)
            z.writestr(filename, img_buf.read())
    
    buffer.seek(0)
    
    # Return the ZIP file
    return send_file(buffer, as_attachment=True, download_name='graphs.zip', mimetype='application/zip')


if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)
