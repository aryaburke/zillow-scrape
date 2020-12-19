import json
import zillow




def hello(event, context):
    #this function runs on deploy
    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "input": "Deployment successful!"
    }

    response = {
        "statusCode": 200,
        "body": json.dumps(body)
    }

    return response


def scrape(event, context):
    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "input": zillow.main()
    }

    response = {
        "statusCode": 200,
        "body": json.dumps(body)
    }

    return response