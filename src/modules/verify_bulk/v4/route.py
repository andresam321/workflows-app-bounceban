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
    # Get the task ID
    task_id = data.get("id")
    if not task_id:
        return Response(
            data={"error": "Task ID is required"},
            metadata={"status": "failed"}
        )
    
    # Get optional parameters
    offset = data.get("offset", 0)
    limit = data.get("limit", 1000)
    filter_status = data.get("filter_status", "all")
    
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
    
    # Validate filter status
    valid_filters = ["all", "deliverable", "undeliverable", "risky", "unknown"]
    if filter_status not in valid_filters:
        return Response(
            data={"error": f"Filter status must be one of: {', '.join(valid_filters)}"},
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
    
    # BounceBan API endpoint for retrieving bulk results in JSON
    url = "https://api.bounceban.com/v1/verify/bulk/dump"
    
    # Headers for BounceBan API (using Authorization without Bearer prefix)
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    
    # Query parameters
    params = {
        "id": task_id
    }
    
    if filter_status != "all":
        params["filter"] = filter_status
    
    try:
        # Make GET request to BounceBan API
        response = requests.get(url, headers=headers, params=params, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        print(f"API response: {result}")  # Debugging line to check API response structure
        # Extract results data from response
        results_data = {
            "task_id": task_id,
            "total_results": len(result.get("items", [])),
            "returned_results": len(result.get("items", [])),
            "offset": offset,
            "limit": limit,
            "filter_status": "all",
            "results": []
        }

        for email_result in result.get("items", []):
            processed_result = {
                "email": email_result.get("email"),
                "result": email_result.get("result"),
                "result_code": email_result.get("result_code"),
                "score": email_result.get("score"),
                "is_catchall": email_result.get("is_catchall"),
                "is_disposable": email_result.get("is_disposable"),
                "is_role": email_result.get("is_role"),
                "is_free": email_result.get("is_free"),
                "is_seg_protected": email_result.get("is_seg_protected"),
                "message": email_result.get("message"),
                "mx_records": email_result.get("mx_records"),
                "smtp_provider": email_result.get("smtp_provider"),
                "verified_at": email_result.get("verify_at")  # Notice: it's 'verify_at' not 'verified_at'
            }
            results_data["results"].append(processed_result)

        return Response(
            data=results_data,
            metadata={"status": "success"}
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
