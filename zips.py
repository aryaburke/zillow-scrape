import csv

FOIL_STATES = ["NY","VT","NH","ME","NV","AZ","NM","CA","CO","UT","OR","SC"]

def all_zips():
    #all_zips reads the us_zipdata.csv file from geonames.org and returns a list of all US zipcodes
    zips = []
    with open("us_zipdata.csv") as readfile:
        data = csv.reader(readfile, delimiter="\t")
        for row in data:
            zips.append(row[1])
    return zips

def foil_zips():
    #NY, VT, NH, ME, NV, AZ, NM, CA, CO, UT, OR, SC
    zips = []
    with open("us_zipdata.csv") as readfile:
        data = csv.reader(readfile, delimiter="\t")
        for row in data:
            if row[4] in FOIL_STATES:
                zips.append(row[1])
    return zips
