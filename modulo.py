#!/usr/bin/python

import csv
import io

OUTPUT_FORMAT = ["Date","Time","Name","Type","Gross","From Email Address"]

def get_payment_amount_from_row(row):
    return float(row['Gross'].replace(',', ''))

with io.open('paypal.csv', 'r', encoding='utf-8-sig') as payment_file:
    payment_reader = csv.DictReader(payment_file)
    with io.open('filtered_payments.csv', 'w', encoding='utf-8') as output_file:
        writer = csv.DictWriter(output_file, OUTPUT_FORMAT, extrasaction='ignore')
        writer.writeheader()
        for row in payment_reader:
            amount = get_payment_amount_from_row(row)
            row_type = row["Type"]
            if amount % 50 == 0 and row_type != "General Withdrawal":
                writer.writerow(row)
