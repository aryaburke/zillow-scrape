import json
import zillow


def hello(event, context):
    #this function runs on deploy
    body = {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "input": zillow.main()
    }

    response = {
        "statusCode": 200,
        "body": json.dumps(body)
    }

    return response

    # Use this code if you don't use the http event with the LAMBDA-PROXY
    # integration
    """
    return {
        "message": "Go Serverless v1.0! Your function executed successfully!",
        "event": event
    }
    """
