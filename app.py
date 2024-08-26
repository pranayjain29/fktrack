from flask import Flask, request, render_template, send_file, url_for, jsonify, send_file, redirect
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
import zipfile

import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import zipfile
from supabase import create_client, Client
from concurrent.futures import ThreadPoolExecutor

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from email.mime.application import MIMEApplication

from analytical_report import create_pdf_report


app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
SUPABASE_URL = 'https://wutogxoedilgjjjhrqjq.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind1dG9neG9lZGlsZ2pqamhycWpxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjM2MjcxMzMsImV4cCI6MjAzOTIwMzEzM30.nZbd5s9G5Xsp4oXvLOlpcWmVoVb_uhBJefRx803FWMY'
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
executor = ThreadPoolExecutor(max_workers=2)
global session
session = None

@app.route('/')
def home():
    global session
    if session:
        print(session.user.email)
        return render_template('index.html')
    return render_template('login.html')

@app.route('/home', methods=['GET', 'POST'])
def login():
    global session
    if session:
        return render_template('index.html')
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        session = supabase.auth.sign_in_with_password({ "email": email, "password": password })
        sender_mail = session.user.email
        logging.info(f"Logged in: {sender_mail}")
    return render_template('index.html')

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

def clean_price(price_text):
    # Remove ₹ symbol and commas, then convert to float
    cleaned_price = re.sub(r'[₹,]', '', price_text)
    try:
        price = float(cleaned_price)
    except ValueError:
        price = 0
    return price

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

def send_excel_via_email(sender_email, sender_password, receiver_email, subject, body, pdf_buffer, file_buffer):
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    pdf_part = MIMEApplication(pdf_buffer.read(), Name="Market_Report.pdf")
    pdf_part['Content-Disposition'] = 'attachment; filename="Market_Report.pdf"'
    msg.attach(pdf_part)

    part = MIMEApplication(file_buffer.read(), Name="report.xlsx")
    part['Content-Disposition'] = 'attachment; filename="report.xlsx"'
    msg.attach(part)

    print("File Attached")
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        print("Inside Server")
        #server.starttls(timeout=10)
        #print("TTLS Done")
        server.login(sender_email, sender_password)
        print("Logged in successfully.")
        server.sendmail(sender_email, receiver_email, msg.as_string())
        print("Email sent successfully.")
        
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

    connector = aiohttp.TCPConnector(limit=50)  # Increase the number of connections
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch(session, f"https://www.flipkart.com/product/p/itme?pid={FSN}") for FSN in FSN_list]
        responses = await asyncio.gather(*tasks)

        for idx, html in enumerate(responses):
            progress = int((idx + 1) / total_fsns * 100)

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

            seller_rating = float(seller_name[-3:]) if seller_name[-3:].replace('.', '').isdigit() else 0.0
            seller_name = seller_name[:-3].strip()

            parameter_ratings = await extract_parameter_ratings(soup)
            star_ratings = await extract_star_ratings(soup)

            highlight_div = soup.find('div', class_='vN8oQA')
            parent_div = highlight_div.find_next_sibling('div', class_='xFVion') if highlight_div else None
            list_items = parent_div.find_all('li', class_='_7eSDEz') if parent_div else []
            features = {f'feature{i+1}': li.text.strip() for i, li in enumerate(list_items)}

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
                **parameter_ratings,
                **features
            })

    df = pd.DataFrame(all_data)
    return df


@app.route('/scrape', methods=['POST'])
async def scrape():
    if not session:
        return login
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

    connector = aiohttp.TCPConnector(limit=50)  # Increase the number of connections
    async with aiohttp.ClientSession(connector=connector) as session:
        
        tasks = [fetch(session, f"https://www.flipkart.com/product/p/itme?pid={pid}") for pid in pid_list]
        html_responses = await asyncio.gather(*tasks)

        tasks_mob = [fetch_mob(session, f"https://www.flipkart.com/product/p/itme?pid={pid}") for pid in pid_list]
        html_mob_responses = await asyncio.gather(*tasks_mob)

        total_fsns = len(pid_list)
        for i, pid in enumerate(pid_list):
            progress = int((i + 1) / total_fsns * 100)

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

            seller_rating = float(seller_name[-3:]) if seller_name[-3:].replace('.', '').isdigit() else 0.0
            seller_name = seller_name[:-3].strip()

            parameter_ratings = await extract_parameter_ratings(soup)
            star_ratings = await extract_star_ratings(soup)

            highlight_div = soup.find('div', class_='vN8oQA')
            parent_div = highlight_div.find_next_sibling('div', class_='xFVion') if highlight_div else None
            list_items = parent_div.find_all('li', class_='_7eSDEz') if parent_div else []
            features = {f'feature{i+1}': li.text.strip() for i, li in enumerate(list_items)}

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
                **features,
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
    global session
    query = request.form['query']
    pages = int(request.form['num_pages'])
    sort_option = request.form['sort_option']

    executor.submit(asyncio.run, run_scraping_task(query, sort_option, pages, session.user.email))

    # Display the message and end the client-side connection
    logging.info("Your report will be sent through mail")
    return render_template('through_mail.html')

async def run_scraping_task(query, sort_option, pages, sender_mail):
    start_time = time.time()
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
    file_buffer = io.BytesIO()
    df.to_excel(file_buffer, index=False)
    file_buffer.seek(0)

    pdf_buffer = create_pdf_report(query, pages, df)

    logging.info(f"Sending to: {sender_mail}")
    send_excel_via_email(sender_email="pranayjain354@gmail.com", sender_password="qoae qasu ozeo qdhe", receiver_email=sender_mail,
                             subject="Competition Scrapper Report", body="Congratulations! You can now download the attached report from below.", pdf_buffer=pdf_buffer, file_buffer = file_buffer)
    logging.info("File Sent")
    os.remove('flipkart_comp_data.xlsx')
    return render_template('competitor_data.html', fetch_runtime=run_timee, fetch_download_link=url_for('download_file_comp'), analysis_link=url_for('analysis'))
    
@app.route('/competition')
def index2():
    global session
    if not session:
        return redirect(url_for('home'))

    return render_template('competitor_data.html')

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


if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)
