import csv
import dateutil.parser as dateparser
import io
from nameparser import HumanName
import re

SURVEY_FORMAT = ["submission_date","surveyee_first_name","surveyee_last_name","surveyee_email","surveyee_phone",
        "surveyee_address1","surveyee_address2","surveyee_city","surveyee_state","surveyee_zip","surveyee_country",
        "products","payer_info","payer_address","player1_first_name","player1_last_name","player1_email",
        "player2_first_name","player2_last_name","player2_email","player3_first_name","player3_last_name",
        "player3_email","player4_first_name","player4_last_name","player4_email","player5_first_name",
        "player5_last_name","player5_email"]
OUTPUT_FORMAT = ["Last name", "First name", "Email", "Group number", "Group members", "Paid amount", "Group amount",
        "Payees", "Verification status", "Phone", "Address"]
AMOUNT_MATCHER = re.compile("Total: (\d+\.\d+)")

NAME_HACKS = {"Bari Specter": "Bari Spector",
        "Liy Zoberman": "Lily Zoberman"}

class Payment:
    def __init__(self, payer, amount, verified = False, time = None):
        self.name = payer
        self.amount = amount
        self.verified = verified
        self.time = time

    def __str__(self):
        return str({"name": self.name, "amount": self.amount, "verified": self.verified})

    def __gt__(self, other):
        if other == None or other.time == None:
            return self
        if self.time == None:
            return other
        return self.time > other.time


class Attendee:
    def __init__(self, name = "", email = "", phone = "", address = "", amount = 0):
        self.name = name
        self.email = email
        self.phone = phone
        self.address = address
        self.amount = amount

    def __str__(self):
        return str({"name": self.name, "email": self.email, "phone": self.phone, "address": self.address})

    def __gt__(self, other):
        self_name_obj = HumanName(self.name)
        other_name_obj = HumanName(other.name)
        if self_name_obj.last == other_name_obj.last:
            return self_name_obj.first > other_name_obj.first
        return self_name_obj.last > other_name_obj.last

class Group:
    def __init__(self, attendees = [], payments = []):
        self.attendees = {attendee.name: attendee for attendee in attendees}
        self.payments = {payment.name: payment for payment in payments}

    def __str__(self):
        return str({"attendees": self.attendees, "payments": self.payments})

def normalize_name(raw_name):
    name_obj = HumanName(raw_name)
    name_obj.capitalize(force=True)
    name_before_hacks = name_obj.first + " " + name_obj.last
    return NAME_HACKS.get(name_before_hacks, name_before_hacks)

def get_name_from_row(row, prefix):
    return normalize_name(row[prefix + '_first_name'] + " " + row[prefix + '_last_name'])

def get_payment_amount_from_row(row):
    return float(row['Gross'].replace(',', ''))

def merge_attendees(first, other):
    if not first:
        return other
    if not other:
        return first

    merged_values = {}
    for key, value in first.__dict__.items():
        sanitized_value = getattr(first, key)
        if isinstance(sanitized_value, str):
            sanitized_value = sanitized_value.strip()

        if sanitized_value:
            merged_values[key] = getattr(first, key)
        else:
            merged_values[key] = getattr(other, key)

    attendee = Attendee()
    for key, value in merged_values.items():
        setattr(attendee, key, value)

    return attendee

# Read payments by who made them
payments_by_name = {}
with io.open('paypal.csv', 'r', encoding='utf-8') as payment_file:
    payment_reader = csv.DictReader(payment_file)
    for row in payment_reader:
        amount = get_payment_amount_from_row(row)
        if amount % 50 == 0:
            name = normalize_name(row['Name'])
            payment = Payment(name, amount, True)
            payments_by_name[name] = payment

# Dedupe rows by name
deduped_rows_by_name = {}
with io.open('Tickets-2019.csv', 'r', encoding='utf-8') as survey_file:
    survey_reader = csv.DictReader(survey_file, SURVEY_FORMAT)
    skipped_first_row = False
    for row in survey_reader:
        if not skipped_first_row:
            skipped_first_row = True
            continue

        surveyee_name = get_name_from_row(row, "surveyee")
        existing_row = deduped_rows_by_name.pop(surveyee_name, None)
        if existing_row and dateparser.parse(existing_row['submission_date']) > dateparser.parse(row['submission_date']):
            surveyee_name = get_name_from_row(existing_row, "surveyee")
            deduped_rows_by_name[surveyee_name] = existing_row
        else:
            deduped_rows_by_name[surveyee_name] = row

# Create and merge groups
groups_by_name = {}
rows_ascending_time = sorted(deduped_rows_by_name.values(), key = lambda row: dateparser.parse(row['submission_date']))
for row in rows_ascending_time:
    # Generate all players
    group_members_by_name = {}
    for player_num in range(1, 6):
        player_prefix = "player" + str(player_num)
        player_name = get_name_from_row(row, player_prefix).strip()
        if not player_name:
            continue
        group_members_by_name[player_name] = Attendee(player_name, row[player_prefix + "_email"])

    surveyee_name = get_name_from_row(row, "surveyee")
    address_list = [row["surveyee_address1"], row["surveyee_address2"], row["surveyee_city"], row["surveyee_state"],
            row["surveyee_zip"], row["surveyee_country"]]
    address = ", ".join(filter(None, address_list))
    row_amount = float(re.search(AMOUNT_MATCHER, row["products"]).group(1))
    group_members_by_name[surveyee_name] = Attendee(surveyee_name, row["surveyee_email"], row["surveyee_phone"],
            address, row_amount)
    row_time = dateparser.parse(row['submission_date'])

    # Generate payment info
    payment_verified = False
    if surveyee_name in payments_by_name:
        payment = payments_by_name[surveyee_name]
        if payment.amount == row_amount:
           payment_verified = True
    payment = Payment(surveyee_name, row_amount, payment_verified, row_time)

    group = Group(group_members_by_name.values(), [payment])

    # find group with these people in it
    existing_group = None
    for name in group_members_by_name.keys():
        matching_group = groups_by_name.get(name, None)
        if matching_group:
            new_group_name_set = frozenset(group_members_by_name.keys())
            matching_group_name_set = frozenset(matching_group.attendees.keys())
            print("new_group is " + str(new_group_name_set) + " and old group is " + str(matching_group_name_set))
            if new_group_name_set.issubset(matching_group_name_set) or matching_group_name_set.issubset(new_group_name_set):
                print("found match!")
                existing_group = matching_group
                break

    # group exists, so merge data
    if existing_group:
        merged_attendees = []
        merged_attendees_names = frozenset(existing_group.attendees.keys()).union(frozenset(group.attendees.keys()))
        for attendee_name in merged_attendees_names:
            existing_attendee = existing_group.attendees.get(attendee_name, None)
            new_attendee = group.attendees.get(attendee_name, None)
            merged_attendees.append(merge_attendees(existing_attendee, new_attendee))

        merged_payments = list(existing_group.payments.values())
        merged_payments.append(payment)
        group = Group(merged_attendees, merged_payments)

    # put group under all attendees' names
    for name in group.attendees.keys():
        groups_by_name[name] = group

groups = frozenset(groups_by_name.values())
sorted_groups = sorted(groups, key = lambda group: sorted(group.payments.values())[0])
group_id = 1
for group in sorted_groups:
    debug_str = "for group " + str(group_id)
    for attendee in group.attendees.values():
        debug_str += " attendee is " + str(attendee)
    for payment in group.payments.values():
        debug_str += " payment is " + str(payment)
    print(debug_str)
    group_id += 1

group_id = 1
with io.open('output.csv', 'w', encoding='utf-8') as output_file:
    writer = csv.DictWriter(output_file, OUTPUT_FORMAT)
    writer.writeheader()
    for group in sorted_groups:
        group_members = ", ".join(group.attendees.keys())
        paid_amount = 0
        payees = []
        seen_unverified_payment = False

        for payment in group.payments.values():
            paid_amount += payment.amount
            payees.append(payment.name)
            seen_unverified_payment |= not payment.verified

        verfication_status = ''
        if seen_unverified_payment:
            verification_status = "Some unverified"
        else:
            verification_status = "All verified"
        payee_str = ", ".join(payees)
        paid_amount_str = '${:,.2f}'.format(paid_amount)

        for attendee in group.attendees.values():
            individual_paid_str = '${:,.2f}'.format(attendee.amount)

            name_obj = HumanName(attendee.name)
            output_row = {"Email": attendee.email, "Phone": attendee.phone, "Last name": name_obj.last,
                    "Address": attendee.address, "Paid amount": individual_paid_str, "Group number": group_id,
                    "Group members": group_members, "Group amount":  paid_amount_str, "Payees": payee_str,
                    "Verification status": verification_status, "First name": name_obj.first}
            writer.writerow(output_row)

        group_id += 1
