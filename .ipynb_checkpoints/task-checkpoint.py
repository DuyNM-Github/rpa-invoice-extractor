# +
"""Template robot with Python."""
from selenium import webdriver
from selenium.webdriver import Firefox
from selenium.webdriver.common.by import By
from PIL import Image
import pytesseract
import urllib.request
import re
import json
import os, shutil

driver = Firefox()
listOfRows = []
listOfCompAbbreviation = ["ASSOC", "BROS", "CIE", "CORP", "CO", "INC",
                          "LTD", "MFG", "MFRS", "JSC", "LLC"]
date_regex = r"(?:[0-9]{4}\/*[0-9]{2}\/*[0-9]{2})|(?:[0-9]{4}-*[0-9]{2}-*[0-9]{2})|(?:[A-Za-z]{3}.[0-9]{1,2}.*[0-9]{4})|(?:[0-9]{2}.*[A-Za-z]{3}.*[0-9]{4}$)"
main_page_url = "http://rpachallengeocr.azurewebsites.net"

driver.get(main_page_url)


# -

def get_invoice_list():
    next_button = driver.find_element(By.CLASS_NAME, "next")
    table_row = driver.find_elements_by_xpath('//*[@id="tableSandbox"]/tbody/tr')
    for index in range(1, len(table_row) + 1, 1):
        row_data = driver.find_elements_by_xpath(f'//*[@id="tableSandbox"]/tbody/tr[{index}]/td')
        data_dict = {
                        "ID": row_data[1].text,
                        "DueDate": row_data[2].text,
                        "Invoice": row_data[3].find_element(By.TAG_NAME, 'a')
                                             .get_attribute('href')
                    }
        listOfRows.append(data_dict)
    if 'disabled' not in next_button.get_attribute('class'):
        next_button.click()
        get_invoice_list()


def data_to_json():
    with open('./output/invoices.json', 'w', encoding='utf-8') as writer:
        json.dump(listOfRows, writer, indent=4)


def extract_data_from_invoice_images():
    for row in listOfRows:
        driver.get(row["Invoice"])
        # Download the image from the site
        src = driver.find_element(By.TAG_NAME, 'img').get_attribute('src')
        urllib.request.urlretrieve(src, f'./temp/{listOfRows[0]["ID"]}.png')
        invoice = Image.open(f'./temp/{listOfRows[0]["ID"]}.png')
        # Use tesseract-ocr lib to extract text from the image
        # Format extracted string to a List and Clean it up
        extracted_str = (pytesseract.image_to_string(invoice)).strip().splitlines()
        extracted_str = [line for line in extracted_str if line.strip() != '']
        # Replace the Invoice with extracted data in a Dictationary
        row["Invoice"] = grab_relevant_data(extracted_str)
    driver.get(main_page_url)
    print(listOfRows)


def grab_relevant_data(extracted_str):
    comp_name, invoice_num, invoice_date, total_due = None, None, None, None
    for line in extracted_str:
        if invoice_num is None and line.find("#") != -1:
            temp = line.replace(" ", "")
            regex_search = (re.search(r"#", temp)).span()
            invoice_num = temp[regex_search[0]:]
        if comp_name is None:
            for abbrev in listOfCompAbbreviation:
                potential_str = line.upper()
                regex_search = re.search((r"({})\.*".format(abbrev)), potential_str)
                if regex_search is not None and comp_name is None:
                    comp_name = potential_str[:regex_search.span()[1]]
        if (line.upper()).find("TOTAL") != -1:
            regex_search = re.search(r"(Total|TOTAL|total)*\s?\$?[0-9]*", line)
            if regex_search is not None:
                temp = line.split(" ")
                if temp[1].find("$") != -1:
                    total_due = temp[1].replace("$", "")
                else:
                    total_due = temp[1]
        if invoice_date is None and re.search(date_regex, line) is not None:
            search_result = re.search(date_regex, line)
            invoice_date = line[search_result.span()[0]:]
    return (invoice_num, comp_name, total_due, invoice_date)


def clean_temp():
    folder = './temp'
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))


if __name__ == "__main__":
    get_invoice_list()
    extract_data_from_invoice_images()
    data_to_json()
    clean_temp()
