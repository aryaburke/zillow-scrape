from lxml import html
import requests
import unicodecsv as csv
import argparse
import json
from urllib.request import Request, urlopen

BED_COUNT = 2
BATH_COUNT = 2
MAX_PRICE = 300

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


def write_data_to_csv(data):
    # saving scraped data to csv.

    with open("properties-%s.csv" % (zipcode), 'wb') as csvfile:
        fieldnames = ['title', 'address', 'city', 'state', 'postal_code', 'price', 'zestimate', 'zestimate_rent', 'price_to_rent_ratio', 'facts and features', 'real estate provider', 'url']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)


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

        for properties in search_results:
            address = properties.get('addressWithZip')
            property_info = properties.get('hdpData', {}).get('homeInfo')
            city = property_info.get('city')
            state = property_info.get('state')
            postal_code = property_info.get('zipcode')
            price = properties.get('price')
            zestimate = properties.get('zestimate')
            bedrooms = properties.get('beds')
            bathrooms = properties.get('baths')
            area = properties.get('area')
            info = f'{bedrooms} bds, {bathrooms} ba ,{area} sqft'
            broker = properties.get('brokerName')
            property_url = properties.get('detailUrl')
            title = properties.get('statusText')
            zestimate_rent = properties.get('hdpData').get('homeInfo').get('rentZestimate')
            price_to_rent_ratio = ""

            if zestimate_rent and zestimate:
              price_to_rent_ratio = round(zestimate_rent / zestimate * 100, 2)

            data = {'address': address,
                    'city': city,
                    'state': state,
                    'postal_code': postal_code,
                    'price': price,
                    'zestimate': zestimate,
                    'zestimate_rent': zestimate_rent,
                    'price_to_rent_ratio': price_to_rent_ratio,
                    'facts and features': info,
                    'real estate provider': broker,
                    'url': property_url,
                    'title': title}
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
    for page in range(1, 4):
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

if __name__ == "__main__":
    # Reading arguments

    argparser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    argparser.add_argument('zipcode', help='')
    sortorder_help = """
    available sort orders are :
    newest : Latest property details,
    cheapest : Properties with cheapest price
    """

    argparser.add_argument('sort', nargs='?', help=sortorder_help, default='Homes For You')
    args = argparser.parse_args()
    zipcode = args.zipcode
    sort = args.sort
    print ("Fetching data for %s" % (zipcode))
    scraped_data = parse(zipcode, sort)
    if scraped_data:
        print ("Writing data to output file")
        write_data_to_csv(scraped_data)
