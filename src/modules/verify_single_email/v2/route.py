from workflows_cdk import Request, Response
from flask import request as flask_request
from main import router
import os
import requests

@router.route("/execute", methods=["POST", "GET"])
def execute():
    # request = Request(flask_request)
    # data = request.data
    data = flask_request.get_json(force=True)
    # Get the verification ID
    print(f"Received data: {data}")
    verification_id = data.get("id")
    if not verification_id:
        return Response(
            data={"error": "Verification ID is required"},
            metadata={"status": "failed"}
        )
    print(f"Received verification ID: {verification_id}")
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
    
    # BounceBan API endpoint for retrieving verification results
    url = "https://api.bounceban.com/v1/verify/single/status"
    
    # Headers for BounceBan API (using Authorization without Bearer prefix)
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    
    # Query parameters
    params = {
        "id": verification_id
    }
    print(f"Making request to BounceBan API with params: {params}")
    try:
        # Make GET request to BounceBan API
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        print(f"API response: {result}")
        # Extract verification result data
        verification_result = {
            "verification_id": verification_id,
            "email": result.get("email"),
            "status": result.get("status"),
            "result": result.get("result"),
            "result_code": result.get("result_code"),
            "score": result.get("score"),
            "is_catchall": result.get("is_catchall"),
            "is_disposable": result.get("is_disposable"),
            "is_role": result.get("is_role"),
            "is_free": result.get("is_free"),
            "is_seg_protected": result.get("is_seg_protected"),
            "message": result.get("message"),
            "details": result.get("details"),
            "mx_records": result.get("mx_records"),
            "smtp_provider": result.get("smtp_provider"),
            "timestamp": result.get("timestamp"),
            "completed_at": result.get("completed_at")
        }
        
        # Determine metadata status based on verification status
        if result.get("status") == "completed":
            # Map result to metadata status
            if result.get("result") in ["deliverable", "valid"]:
                metadata_status = "success"
            elif result.get("result") in ["undeliverable", "invalid"]:
                metadata_status = "failed"
            elif result.get("result") in ["risky", "catchall", "unknown"]:
                metadata_status = "success"  # Still success but with warnings
            else:
                metadata_status = "success"
        elif result.get("status") == "processing":
            metadata_status = "still processing"
        else:
            metadata_status = "failed"
        
        return Response(
            data=verification_result,
            metadata={
                "status": metadata_status,
                "verification_status": result.get("result", "unknown")
            }
        )
        
    except requests.exceptions.Timeout:
        return Response(
            data={"error": "Request timeout"},
            metadata={"status": "failed"}
        )
    except requests.exceptions.RequestException as e:
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
