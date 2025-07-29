from workflows_cdk import Request, Response
from flask import request as flask_request
from main import router
import os
import requests
import json

@router.route("/execute", methods=["POST", "GET"])
def execute():
    # request = Request(flask_request)
    # data = request.data
    data = flask_request.get_json(force=True)
    print(f"Request Data: {data}")
    # Get the task ID
    emails = data.get("emails")
    if not emails or not isinstance(emails, list) or not all(isinstance(e, str) and "@" in e for e in emails):
        return Response(
            data={"error": "A valid list of email addresses is required"},
            metadata={"status": "failed"}
        )
    task_id = data.get("id")
    if not task_id:
        return Response(
            data={"error": "Task ID is required"},
            metadata={"status": "failed"}
        )
    print(f"Task ID: {task_id}")
    # Get optional parameters
    offset = data.get("offset", 0)
    limit = data.get("limit", 1000)
    
    # Validate pagination parameters
    if offset < 0:
        return Response(
            data={"error": "Offset must be 0 or greater"},
            metadata={"status": "failed"}
        )
    
    if limit < 1 or limit > 10000:
        return Response(
            data={"error": "Limit must be between 1 and 10000"},
            metadata={"status": "failed"}
        )
    
    # Get API key from connection or environment
    api_key = None
    if data.get("api_connection"):
        api_key = data["api_connection"].get("api_key")
    
    if not api_key:
        api_key = os.environ.get("BOUNCEBAN_API_KEY")
    
    if not api_key:
        return Response(
            data={"error": "API key is required"},
            metadata={"status": "failed"}
        )
    
    # BounceBan API endpoint for requesting bulk results
    url = "https://api.bounceban.com/v1/verify/bulk/emails"
    
    # Headers for BounceBan API (using Authorization without Bearer prefix)
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    
    # Request body
    payload = {
        "id": task_id,
        "emails": emails,
    }
    print(f"Payload: {payload}")
    try:
        # Make POST request to BounceBan API
        print(f"URL: {url}")
        print(f"Headers: {headers}")
        print(f"Payload: {json.dumps(payload)}")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        print(f"API Response: {result}")
        # Extract result generation data from response
        result_data = {
            "id": task_id,
            "request_id": result.get("request_id"),
            "status": result.get("status"),
            "message": result.get("message", "Result generation requested successfully"),
            "total_emails": result.get("total_emails", 0),
            "offset": offset,
            "limit": limit,
            "processing_time_estimate": result.get("processing_time_estimate"),
            "result_ready": result.get("result_ready", False)
        }
        
        # Determine metadata status
        if result.get("result_ready", False):
            metadata_status = "success"
        elif result.get("status") == "processing":
            metadata_status = "still processing"
        else:
            metadata_status = "success"  # Request was successful even if results aren't ready
        
        return Response(
            data=result_data,
            metadata={"status": metadata_status}
        )
        
    except requests.exceptions.Timeout:
        return Response(
            data={"error": "Request timeout"},
            metadata={"status": "failed"}
        )
    except requests.exceptions.RequestException as e:
        print(f"Full response: {e.response.text if e.response else 'No response'}")
        return Response(
            data={"error": f"API request failed: {str(e)}"},
            metadata={"status": "failed"}
        )
    except Exception as e:
        return Response(
            data={"error": f"Unexpected error: {str(e)}"},
            metadata={"status": "failed"}
        )


@router.route("/content", methods=["GET", "POST"])
def content():
    """
    This is the function that goes and fetches the necessary data to populate the possible choices in dynamic form fields.
    For example, if you have a module to delete a contact, you would need to fetch the list of contacts to populate the dropdown
    and give the user the choice of which contact to delete.

    An action's form may have multiple dynamic form fields, each with their own possible choices. Because of this, in the /content route,
    you will receive a list of content_object_names, which are the identifiers of the dynamic form fields. A /content route may be called for one or more content_object_names.

    Every data object takes the shape of:
    {
        "value": "value",
        "label": "label"
    }
    
    Args:
        data:
            form_data:
                form_field_name_1: value1
                form_field_name_2: value2
            content_object_names:
                [
                    {   "id": "content_object_name_1"   }
                ]
        credentials:
            connection_data:
                value: (actual value of the connection)

    Return:
        {
            "content_objects": [
                {
                    "content_object_name": "content_object_name_1",
                    "data": [{"value": "value1", "label": "label1"}]
                },
                ...
            ]
        }
    """
    request = Request(flask_request)

    data = request.data

    form_data = data.get("form_data", {})
    content_object_names = data.get("content_object_names", [])
    
    # Extract content object names from objects if needed
    if isinstance(content_object_names, list) and content_object_names and isinstance(content_object_names[0], dict):
        content_object_names = [obj.get("id") for obj in content_object_names if "id" in obj]

    content_objects = [] # this is the list of content objects that will be returned to the frontend

    for content_object_name in content_object_names:
        if content_object_name == "requested_content_object_1":
            # logic here
            data = [
                {"value": "value1", "label": "label1"},
                {"value": "value2", "label": "label2"}
            ]
            content_objects.append({
                    "content_object_name": "requested_content_object_1",
                    "data": data
                })
        elif content_object_name == "requested_content_object_2":
            # logic here
            data = [
                {"value": "value1", "label": "label1"},
                {"value": "value2", "label": "label2"}
            ]
            content_objects.append({
                    "content_object_name": "requested_content_object_2",
                    "data": data
                })
    
    return Response(data={"content_objects": content_objects})
