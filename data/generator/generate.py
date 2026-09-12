import argparse
import csv
import json
import random
from datetime import datetime, timedelta
import os

MERCHANT_VARIANTS = {
    'NETFLIX': ['NETFLIX.COM 8X4F2', 'NETFLIX INC #4471', 'NETFLIX MONTHLY', 'NETFLIX*COM', 'NETFLIX INC'],
    'SPOTIFY': ['SPOTIFY', 'SPOTIFY AB', 'SPOTIFY PREMIUM', 'SPOTIFY.COM AB1234', 'SP * SPOTIFY'],
    'AMAZON PRIME': ['AMAZON PRIME', 'AMAZON.COM PRIME', 'AMZN MKTP PRIME', 'AMAZON PRIME MEMBERSHIP'],
    'ICLOUD': ['APPLE ICLOUD', 'ICLOUD.COM', 'APPLE.COM/BILL ICLOUD', 'APPLE SERVICES ICLOUD'],
    'DROPBOX': ['DROPBOX', 'DROPBOX INC', 'DROPBOX.COM', 'DROPBOX PLUS'],
    'YOUTUBE PREMIUM': ['YOUTUBE PREMIUM', 'GOOGLE YOUTUBE', 'GOOGLE*YOUTUBEPREMIUM', 'YT PREMIUM'],
    'HOTSTAR': ['HOTSTAR', 'DISNEY+ HOTSTAR', 'HOTSTAR PREMIUM', 'HOTSTAR VIP'],
    'LINKEDIN': ['LINKEDIN PREMIUM', 'LINKEDIN.COM PREMIUM', 'LINKEDIN CORP PREMIUM'],
}

ONE_OFF_MERCHANTS = [
    'SWIGGY ORDER 8X4F2', 'ZOMATO FOOD 1234', 'DMART RETAIL #42', 'AMAZON.IN SHOPPING', 
    'FLIPKART ORDER', 'PETROL PUMP #18', 'ATM WITHDRAWAL', 'IRCTC BOOKING 5K291', 
    'MAKEMYTRIP HOTELS', 'UBER TRIP', 'OLA CABS', 'BIG BAZAAR PURCHASE'
]

SUBSCRIPTION_CONFIG = [
    {'merchant': 'NETFLIX', 'cycle_days': 30, 'base_amount': 199.0, 'hike_at_charge': 4, 'new_amount': 249.0},
    {'merchant': 'SPOTIFY', 'cycle_days': 30, 'base_amount': 149.0},
    {'merchant': 'AMAZON PRIME', 'cycle_days': 30, 'base_amount': 299.0},
    {'merchant': 'ICLOUD', 'cycle_days': 30, 'base_amount': 75.0},
    {'merchant': 'YOUTUBE PREMIUM', 'cycle_days': 30, 'base_amount': 129.0, 'hike_at_charge': 3, 'new_amount': 189.0},
    {'merchant': 'DROPBOX', 'cycle_days': 365, 'base_amount': 3500.0},
    {'merchant': 'LINKEDIN', 'cycle_days': 30, 'base_amount': 2200.0},
    {'merchant': 'HOTSTAR', 'cycle_days': 365, 'base_amount': 1499.0},
]

def generate_subscription_charges(merchant, config, start_date, end_date, jitter_days=3, rng=random):
    charges = []
    current_date = start_date
    charge_count = 1
    
    while current_date <= end_date:
        jitter = timedelta(days=rng.randint(-jitter_days, jitter_days))
        charge_date = current_date + jitter
        if charge_date > end_date:
            break
            
        desc = rng.choice(MERCHANT_VARIANTS[merchant])
        
        amount = config['base_amount']
        if 'hike_at_charge' in config and charge_count >= config['hike_at_charge']:
            amount = config['new_amount']
            
        charges.append((charge_date.strftime('%Y-%m-%d'), desc, f"{amount:.2f}"))
        
        current_date += timedelta(days=config['cycle_days'])
        charge_count += 1
        
    return charges

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='transactions.csv')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--months', type=int, default=12)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30 * args.months)

    all_transactions = []
    ground_truth = []

    for config in SUBSCRIPTION_CONFIG:
        merchant = config['merchant']
        sub_start_date = start_date + timedelta(days=rng.randint(0, 60))
        charges = generate_subscription_charges(merchant, config, sub_start_date, end_date, rng=rng)
        all_transactions.extend(charges)
        if charges:
            ground_truth.append({
                'merchant': merchant,
                'charges_count': len(charges)
            })

    # One-offs
    num_one_offs = rng.randint(30, 50)
    for _ in range(num_one_offs):
        charge_date = start_date + timedelta(days=rng.randint(0, (end_date - start_date).days))
        desc = rng.choice(ONE_OFF_MERCHANTS)
        amount = round(rng.uniform(50.0, 5000.0), 2)
        all_transactions.append((charge_date.strftime('%Y-%m-%d'), desc, f"{amount:.2f}"))

    all_transactions.sort(key=lambda x: x[0])

    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or '.', exist_ok=True)
    
    with open(args.output, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Description', 'Amount'])
        writer.writerows(all_transactions)

    gt_file = os.path.splitext(args.output)[0] + '_truth.json'
    with open(gt_file, 'w') as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Generated {len(all_transactions)} transactions.")
    print(f"Subscriptions generated: {len(ground_truth)}")
    print(f"Saved CSV to {args.output} and ground truth to {gt_file}")

if __name__ == '__main__':
    main()
