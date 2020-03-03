#!/usr/bin/python

WRITE_FORMAT = ["Date","Time","Name","Gross","From Email Address"]

import io
import csv

def get_payment_amount_from_row(row):
    return float(row['Gross'].replace(',', ''))

with io.open('paypal.csv', 'r', encoding='utf-8-sig') as csvfile:
    with io.open('filtered_output.csv', 'w', encoding='utf-8') as write_file:
        reader = csv.DictReader(csvfile)
        writer = csv.DictWriter(write_file, WRITE_FORMAT, extrasaction='ignore')
        writer.writeheader()
        for row in reader:
            amount = get_payment_amount_from_row(row)
            if amount % 5 == 0 and amount > 5:
                print("Name is " + row['Name'] + " and amount is " + row['Gross'] + " and email is " + row['From Email Address'])
                print("row is " + str(row))
                writer.writerow(row)

