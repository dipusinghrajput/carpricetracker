from flask import Flask, send_file, request, jsonify
import datetime
import os
import pandas as pd
from playwright.sync_api import sync_playwright
from twilio.rest import Client

app = Flask(__name__)

CSV_FILE = "car_prices.csv"

# Twilio credentials (store securely)
TWILIO_SID = "AC43f6d3997e2b67711563fa6a3204a954"
TWILIO_AUTH_TOKEN = "57ea0e67f0491a8f2c536c82bc2fbbc7"
TWILIO_PHONE_NUMBER = "+19302124403"

# Car details with selectors
CARS = [
    {"name": "Hyundai Creta", "url": "https://www.cardekho.com/hyundai/creta", 
     "selector": "#rf01 > div.app-content > div > main > div.overviewTop.overviewTopv.bottom > div > div.price"},
    
    {"name": "Maruti Swift", "url": "https://www.carwale.com/maruti-suzuki-cars/swift/", 
     "selector": "#root > div:nth-child(3) > div.o-bWHzMb.o-ducbvd.o-cglRxs.YONMcZ.o-fpkJwH.o-dCyDMp > div > section > div.o-ItVGT.o-bIMsfE.o-eFudgX.o-czEIGQ.o-eKWNKE.o-fBNTVC.o-chzWeu.o-cpnuEd.o-bqHweY > div.o-fznVCs.o-cgFpsP.o-fzptZB > div.o-dEJOrr.o-efHQCX.o-biwSqu.o-fznJDS.o-fznJzb.o-bKazct.o-cpnuEd > div:nth-child(1) > span"}
]

def save_to_csv(data):
    """Save scraped data to CSV."""
    file_exists = os.path.isfile(CSV_FILE)
    df = pd.DataFrame(data, columns=["Timestamp", "Car", "Scraped Price", "Target Price"])
    df.to_csv(CSV_FILE, mode='a', index=False, header=not file_exists)

def get_price(url, selector):
    """Scrape car price from website."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60000)
            page.wait_for_selector(selector, timeout=5000)
            price_text = page.locator(selector).text_content()
            browser.close()
            
            # Extract digits from price string
            price = int("".join(filter(str.isdigit, price_text)))
            return price
    except Exception as e:
        print(f"Error fetching price from {url}: {e}")
        return None

def send_sms(phone, car, price):
    """Send SMS alert using Twilio."""
    client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
    message = f"\U0001F697 Price Drop Alert! {car} is now ₹{price}. Check it out!"
    try:
        client.messages.create(body=message, from_=TWILIO_PHONE_NUMBER, to=phone)
        print("SMS sent successfully!")
    except Exception as e:
        print(f"Failed to send SMS: {e}")

@app.route("/")
def home():
    return send_file("index.html")

@app.route("/track-prices", methods=["POST"])
def track_prices():
    """API to track car prices and send alerts."""
    data = request.json
    phone = data.get("phone")
    target_price = data.get("targetPrice")

    # Validate input
    if not phone or not target_price:
        return jsonify({"error": "Phone number and target price are required."}), 400

    try:
        target_price = int(target_price)  # Convert price to integer
    except ValueError:
        return jsonify({"error": "Invalid target price format."}), 400

    alerts = []
    scraped_data = []
    
    for car in CARS:
        price = get_price(car["url"], car["selector"])
        if price:
            scraped_data.append([datetime.datetime.now(), car["name"], price, target_price])
            if abs(price - target_price) <= 25000:  # Price within ±25,000 range
                send_sms(phone, car["name"], price)
                alerts.append(f"\U0001F697 {car['name']} is now ₹{price}!")
    
    if scraped_data:
        save_to_csv(scraped_data)
    
    return jsonify({"alert": "\n".join(alerts) if alerts else "No price changes detected."})

if __name__ == "__main__":
    app.run(debug=True)
