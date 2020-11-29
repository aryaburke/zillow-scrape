import csv

def all_zips():
    #all_zips reads the us_zipdata.csv file from geonames.org and returns a list of all US zipcodes
    zips = []
    with open("us_zipdata.csv") as readfile:
        data = csv.reader(readfile, delimiter="\t")
        for row in data:
            zips.append(row[1])
    return zips