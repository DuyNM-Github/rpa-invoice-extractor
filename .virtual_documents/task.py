"""Template robot with Python."""
from RPA.Browser.Selenium import Selenium
from selenium.webdriver import Firefox
from selenium.webdriver.common.by import By
from RPA.FileSystem import FileSystem
from PIL import Image
import pytesseract
import urllib.request
import re
import os, shutil

driver = Selenium()
lib = FileSystem()
listOfRows = []
listOfCompAbbreviation = ["ASSOC", "BROS", "CIE", "CORP", "CO", "INC",
                          "LTD", "MFG", "MFRS", "JSC", "LLC"]
date_regex = r"(?:[0-9]{4}\/*[0-9]{2}\/*[0-9]{2})|(?:[0-9]{4}-*[0-9]{2}-*[0-9]{2})|(?:[A-Za-z]{3}.[0-9]{1,2}.*[0-9]{4})|(?:[0-9]{2}.*[A-Za-z]{3}.*[0-9]{4}$)"
main_page_url = "http://rpachallengeocr.azurewebsites.net"

driver.open_available_browser(main_page_url)


def initial_check():
    if lib.does_directory_exist('./temp') is False:
        lib.create_directory('./temp', exist_ok=True)
    if lib.does_directory_exist('./output') is False:
        lib.create_directory('./output', exist_ok=True)
    if driver.is_element_visible("class:next") is False:
        driver.go_to(main_page_url)


def get_invoice_list():
    next_button = driver.get_webelement("class:next")
    table_row = driver.find_elements('xpath://*[@id="tableSandbox"]/tbody/tr')
    for index in range(1, len(table_row) + 1, 1):
        row_data = driver.find_elements(f'xpath://*[@id="tableSandbox"]/tbody/tr[{index}]/td')
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


def data_to_csv():
    header = "ID,DueDate,InvoiceNumber,InvoiceDate,CompanyName,Total\n"
    lib.create_file("output/invoices", content=None, encoding='utf-8', overwrite=True)
    lib.append_to_file("output/invoices", header, encoding='utf-8')
    for row in listOfRows:
        ID, DueDate, InvoiceNumber = row["ID"], row["DueDate"], row["Invoice"]["InvoiceNumber"]
        InvoiceDate, CompanyName, Total = row["Invoice"]["InvoiceDate"], row["Invoice"]["CompanyName"], row["Invoice"]["Total"]
        textToWrite = "\"{}\",\"{}\",\"{}\",\"{}\",\"{}\",\"{}\"\n".format(ID,DueDate,InvoiceNumber,InvoiceDate,CompanyName,Total)
        lib.append_to_file("output/invoices", textToWrite, encoding='utf-8')
    if lib.does_file_exist("output/invoices.csv") is True:
        lib.remove_file("output/invoices.csv", missing_ok=True)
    lib.change_file_extension("output/invoices", '.csv')


def extract_data_from_invoice_images():
    for row in listOfRows:
        driver.go_to(row["Invoice"])
        # Download the image from the site
        src = driver.find_element('tag:img').get_attribute('src')
        urllib.request.urlretrieve(src, f'./temp/{listOfRows[0]["ID"]}.png')
        invoice = Image.open(f'./temp/{listOfRows[0]["ID"]}.png')
        # Use tesseract-ocr lib to extract text from the image
        # Format extracted string to a List and Clean it up
        extracted_str = (pytesseract.image_to_string(invoice)).strip().splitlines()
        extracted_str = [line for line in extracted_str if line.strip() != '']
        # Replace the Invoice with extracted data in a Dictationary
        row["Invoice"] = grab_relevant_data(extracted_str)
    print("Finished extracting data")
    driver.go_to(main_page_url)


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
                    total_due = total_due.replace(",", "")
                else:
                    total_due = temp[1].replace(",","")
        if invoice_date is None and re.search(date_regex, line) is not None:
            search_result = re.search(date_regex, line)
            invoice_date = line[search_result.span()[0]:]
    return {"InvoiceNumber":invoice_num, "CompanyName":comp_name, "Total":total_due, "InvoiceDate":invoice_date}


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
    initial_check()
    get_invoice_list()
    extract_data_from_invoice_images()
    data_to_csv()
    clean_temp()
