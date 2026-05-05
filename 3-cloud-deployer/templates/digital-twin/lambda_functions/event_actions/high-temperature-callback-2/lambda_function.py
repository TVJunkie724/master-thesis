"""
High Temperature Callback 2 AWS Lambda Function.

Event action triggered by event-checker when temperature threshold is met.
"""
import json


def lambda_handler(event, context):
    print("Hello from High Temperature Callback 2!")
    print("Event: " + json.dumps(event))
    
    return {
        'statusCode': 200,
        'body': json.dumps('Callback 2 executed')
    }