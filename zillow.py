from lxml import html
import requests
import unicodecsv as csv
import argparse
import json
from urllib.request import Request, urlopen
import boto3
from decimal import *

BED_COUNT = 1
BATH_COUNT = 1
MAX_PRICE = 300

ZIPCODES = [
    "94102",
]

def clean(text):
    if text:
        return ' '.join(' '.join(text).split())
    return None

def get_headers():
    # Creating headers.
    headers = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
               'accept-encoding': 'gzip, deflate, sdch, br',
               'accept-language': 'en-GB,en;q=0.8,en-US;q=0.6,ml;q=0.4',
               'cache-control': 'max-age=0',
               'upgrade-insecure-requests': '1',
               'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.131 Safari/537.36'}
    return headers

def create_url(zipcode, filter, page):
    print("Getting data for page: {0}, bed count: {1}, bath count: {2}".format(page, BED_COUNT, BATH_COUNT))
    # Creating Zillow URL based on the filter.
    if filter == "newest":
        url = "https://www.zillow.com/homes/for_sale/{0}/0_singlestory/days_sort".format(zipcode)
    elif filter == "cheapest":
        url = "https://www.zillow.com/homes/for_sale/{0}/0_singlestory/pricea_sort/".format(zipcode)
    else:
        url = "https://www.zillow.com/homes/for_sale/{0}_rb/{1}-_beds/{2}-_baths/{3}_p/?fromHomePage=true&shouldFireSellPageImplicitClaimGA=false&fromHomePageTab=buy".format(zipcode, BED_COUNT, BATH_COUNT, page)
    print(url)
    return url

def save_to_file(response):
    # saving response to `response.html`
    with open("response.html", 'w') as fp:
        fp.write(response.text)

def get_response(url):
    # Getting response from zillow.com
    for i in range(5):
        response = requests.get(url, headers=get_headers())
        print("Status code received:", response.status_code)
        if response.status_code != 200:
            # saving response to file for debugging purpose.
            save_to_file(response)
            continue
        else:
            save_to_file(response)
            return response
    return None

def get_data_from_json(raw_json_data):
    # getting data from json (type 2 of their A/B testing page)
    #print(raw_json_data)
    cleaned_data = clean(raw_json_data).replace('<!--', "").replace("-->", "")
    #print(cleaned_data)
    properties_list = []
    try:
        json_data = json.loads(cleaned_data)
        search_results = json_data.get('cat1').get('searchResults').get('listResults', [])
        #print(search_results)
        for properties in search_results:
            zpid = properties.get('zpid')
            address = properties.get('address')
            property_info = properties.get('hdpData', {}).get('homeInfo')
            city = property_info.get('city')
            state = property_info.get('state')
            zipcode = property_info.get('zipcode')
            price = properties.get('price')
            zestimate = properties.get('zestimate')
            bedrooms = properties.get('beds')
            bathrooms = Decimal(str(properties.get('baths')))
            area = properties.get('area')
            broker = properties.get('brokerName')
            property_url = properties.get('detailUrl')
            title = properties.get('statusText')
            zestimate_rent = properties.get('hdpData').get('homeInfo').get('rentZestimate')
            price_to_rent_ratio = ""
            hasImage = properties.get('hasImage')
            imgSrc = properties.get('imgSrc')

            if zestimate_rent and zestimate:
              price_to_rent_ratio = Decimal(str(round(zestimate_rent / zestimate * 100, 2)))

            data = {'zpid': zpid,
                    'address': address,
                    'city': city,
                    'state': state,
                    'zipcode': zipcode,
                    'price': price,
                    'zestimate': zestimate,
                    'zestimate_rent': zestimate_rent,
                    'price_to_rent_ratio': price_to_rent_ratio,
                    'bathrooms': bathrooms,
                    'bedrooms': bedrooms,
                    'area': area,
                    'real estate provider': broker,
                    'url': property_url,
                    'title': title,
                    'hasImage': hasImage,
                    'imgSrc': imgSrc}
            properties_list.append(data)

        return properties_list

    except ValueError:
        print("Invalid json")
        return None

def unique(list):
    # intilize a null list
    unique_list = []

    # traverse for all elements
    for x in list:
        # check if exists in unique_list or not
        if x not in unique_list:
            unique_list.append(x)
    return unique_list

def parse(zipcode, filter=None):
    final_data = []
    for page in range(1, 5):
      url = create_url(zipcode, filter, page)
      response = get_response(url)

      if not response:
          print("Failed to fetch the page, please check `response.html` to see the response received from zillow.com.")
          return None

      req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
      webpage = urlopen(req).read()

      parser = html.fromstring(webpage)
      search_results = parser.xpath("//div[@id='search-results']//article")

      if not search_results:
          print("Parsing from json data")
          # identified as type 2 page
          raw_json_data = parser.xpath('//script[@data-zrr-shared-data-key="mobileSearchPageStore"]//text()')
          parsed_data = get_data_from_json(raw_json_data)
          #if parsed_data not in final_data:
          final_data.append(parsed_data)
    # The result is array of array, flatten it
    flattened = [val for sublist in final_data for val in sublist]
    uniq = unique(flattened)
    print("Properties count: {0}".format(len(uniq)))
    return uniq

#below functions written by arya for DynamoDDB




def table_exists(TableName, dbclient=None):
    #returns True if the table TableName exists, False otherwise
    if not dbclient:
        dbclient = boto3.client('dynamodb')
    exists = True
    try:
        dbclient.describe_table(TableName='properties')
    except:
        exists = False
    return exists

def create_properties_table(dynamodb=None):
    #creates the properties table if it doesn't exist
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')
    if not table_exists('properties'):
        table = dynamodb.create_table(
            TableName='properties',
            KeySchema=[
                {
                    'AttributeName': 'zpid',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'zipcode',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'zpid',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'zipcode',
                    'AttributeType': 'S'
                },
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        # Print out some data about the table.
        print("Table status:", table.table_status)

def write_to_properties(zipcode, data, tablename='properties', dynamodb=None):
    #writes the parsed data to a table, defaults to properties
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(tablename)
    for row in data:
        table.put_item(Item=row)

def searchwrite(zips, dynamodb=None, sort="Homes For You"):
    #searches each zipcode in an array of zipcodes and writes it to the properties table
    if not dynamodb:
        dynamodb = boto3.resource('dynamodb')
    create_properties_table(dynamodb)
    for zipcode in zips:
        print ("Fetching data for %s" % (zipcode))
        scraped_data = parse(zipcode, sort)
        #print(scraped_data)
        if scraped_data:
            print ("Writing data to output file")
            write_to_properties(zipcode, scraped_data, dynamodb)
            print("FINISHED {0}".format(zipcode))

if __name__ == "__main__":
    searchwrite(ZIPCODES)

