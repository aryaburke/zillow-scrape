from lxml import html
import requests
import unicodecsv as csv
import argparse
import json
from urllib.request import Request, urlopen
import boto3
from decimal import *
from zips import all_zips, foil_zips
from credentials import AWS_ACCESS_KEY_ID, AWS_REGION, AWS_SECRET_ACCESS_KEY
from time import sleep

TEST_ZIPCODES = [
    "99553",
    "10708",
    "59701",
    "07017",
    "14450",
    "98444",
    "45342"
]

TABLENAME = 'properties'

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
    print("Getting data for page: {0}".format(page))
    if filter == "newest":
        url = "https://www.zillow.com/homes/for_sale/{0}/0_singlestory/days_sort".format(zipcode)
    elif filter == "cheapest":
        url = "https://www.zillow.com/homes/for_sale/{0}/0_singlestory/pricea_sort/".format(zipcode)
    else:
        url = "https://www.zillow.com/homes/for_sale/{0}_rb/{1}_p/?fromHomePage=true&shouldFireSellPageImplicitClaimGA=false&fromHomePageTab=buy".format(zipcode, page)
    return url

def save_to_file(response):
    # saving response to `response.html`
    with open("response.html", 'w') as fp:
        fp.write(response.text)

def get_response(url):
    # Getting response from zillow.com
    for i in range(5):
        response = requests.get(url, headers=get_headers())
        #print("Status code received:", response.status_code)
        if response.status_code != 200:
            print("Status code received:", response.status_code)
            # saving response to file for debugging purpose, commented out because AWS uses read-only filesystem
            # save_to_file(response)
            continue
        else:
            # save_to_file(response)
            return response
    return None

def get_data_from_json(raw_json_data):
    # getting data from json (type 2 of their A/B testing page)
    #print(raw_json_data)
    if raw_json_data:
        cleaned_data = clean(raw_json_data).replace('<!--', "").replace("-->", "")
        #print(cleaned_data)
        properties_list = []
        try:
            json_data = json.loads(cleaned_data)
            if json_data:
                search_results = json_data.get('cat1').get('searchResults').get('listResults', [])
            else:
                search_results = []
            #print(search_results)
            for properties in search_results:
                zpid = properties.get('zpid')
                address = properties.get('address')
                street = properties.get('addressStreet')
                property_info = properties.get('hdpData', {}).get('homeInfo')
                city = property_info.get('city')
                state = property_info.get('state')
                zipcode = property_info.get('zipcode')
                price = properties.get('price')
                zestimate = properties.get('zestimate')
                bedrooms = properties.get('beds')
                if properties.get('baths'):
                    bathrooms = Decimal(str(properties.get('baths')))
                else:
                    bathrooms = 0
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
                        'street': street,
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
                        'broker': broker,
                        'url': property_url,
                        'title': title,
                        'hasImage': hasImage,
                        'imgSrc': imgSrc}
                properties_list.append(data)

            return properties_list

        except ValueError:
            print("Invalid json")
            return None
    else:
        return []

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
    prev_parsed = []
    parsed_data = None
    page = 1
    while parsed_data != prev_parsed:
        #keeps track of previous parsed to check
        prev_parsed = parsed_data
        url = create_url(zipcode, filter, page)
        response = get_response(url)

        if not response:
            print("Failed to fetch the page, please check `response.html` to see the response received from zillow.com.")
            return None
        h = { 'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.90 Safari/537.36' }
        req = Request(url, headers=h)
        #headers={'User-Agent': 'Mozilla/5.0'}
        webpage = urlopen(req).read()

        parser = html.fromstring(webpage)
        search_results = parser.xpath("//div[@id='search-results']//article")

        if not search_results:
            #print("Parsing from json data")
            # identified as type 2 page
            #! this is where there is no data found when deployed on serverless
            raw_json_data = parser.xpath('//script[@data-zrr-shared-data-key="mobileSearchPageStore"]//text()')
            parsed_data = get_data_from_json(raw_json_data)
            #if parsed_data not in final_data:
            final_data.append(parsed_data)
            sleep(60)
        page += 1
    # The result is array of array, flatten it
    flattened = [val for sublist in final_data for val in sublist]
    uniq = unique(flattened)
    print("Properties count: {0}".format(len(uniq)))
    return uniq

#below functions written by arya for DynamoDDB


def create_dynamodb():
    return boto3.resource(service_name='dynamodb', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

def table_exists(tablename, dbclient=None):
    #returns True if the table TableName exists, False otherwise
    if not dbclient:
        dbclient = boto3.client(service_name='dynamodb', region_name=AWS_REGION, aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
    exists = True
    try:
        dbclient.describe_table(TableName=tablename)
    except:
        exists = False
    return exists

def create_table(tablename, dynamodb=None):
    #creates the table if it doesn't exist
    if not dynamodb:
        dynamodb = create_dynamodb()
    if not table_exists(tablename):
        table = dynamodb.create_table(
            TableName=tablename,
            KeySchema=[
                {
                    'AttributeName': 'zpid',
                    'KeyType': 'HASH'
                },
                {
                    'AttributeName': 'state',
                    'KeyType': 'RANGE'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'zpid',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'state',
                    'AttributeType': 'S'
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        # Print out some data about the table.
        print("Table status:", table.table_status)

def write_to_table(zipcode, data, tablename, dynamodb=None):
    #writes the parsed data to a table, defaults to properties
    if not dynamodb:
        dynamodb = create_dynamodb()
    table = dynamodb.Table(tablename)
    for row in data:
        try:
            table.put_item(Item=row)
        except Exception as e:
            raise e

def delete_table(tablename, dynamodb=None):
    if not dynamodb:
        dynamodb = create_dynamodb()
    if table_exists(tablename):
        table = dynamodb.Table(tablename)
        table.delete()


def searchwrite(zips, tablename, dynamodb=None, sort="Homes For You"):
    #searches each zipcode in an array of zipcodes and writes it to the table
    if not dynamodb:
        dynamodb = create_dynamodb()
    #table is deleted and re-created as best way to empty it
    delete_table(tablename=TABLENAME, dynamodb=dynamodb)
    create_table(tablename=TABLENAME, dynamodb=dynamodb)
    #gives table time to create
    sleep(60)
    for zipcode in zips:
        print ("Fetching data for %s" % (zipcode))
        scraped_data = parse(zipcode, sort)
        if scraped_data:
            print ("Writing data to output file")
            write_to_table(zipcode=zipcode, data=scraped_data, tablename=TABLENAME, dynamodb=dynamodb)
            print("FINISHED {0}".format(zipcode))

def test():
    zips = TEST_ZIPCODES
    searchwrite(zips, TABLENAME)
    return "Success!"

def main():
    zips = foil_zips()
    searchwrite(zips, TABLENAME)
    return "Success!"


if __name__ == "__main__":
    main()