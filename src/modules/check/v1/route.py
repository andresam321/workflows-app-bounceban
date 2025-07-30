from workflows_cdk import Request, Response
from flask import request as flask_request
from main import router
import os
import requests

def extract_api_key(api_connection: dict) -> str:
    if not api_connection:
        return None
    return api_connection.get("connection_data", {}).get("value", {}).get("api_key_bearer")

@router.route("/execute", methods=["POST", "GET"])
def execute():
    # Parse request JSON
    data = flask_request.get_json(force=True)

    # Get the input to check (email or domain)
    query = data.get("query")
    if not query:
        return Response(
            data={"error": "Email or domain is required."},
            metadata={"status": "failed"}
        )

    # Extract API key from connection object or environment
    api_key = None
    if data.get("api_connection"):
        connection_data = data["api_connection"].get("connection_data", {})
        api_key = connection_data.get("value") or data["api_connection"].get("api_key")

    if not api_key:
        api_key = os.environ.get("BOUNCEBAN_API_KEY")

    if not api_key:
        return Response(
            data={"error": "API key is required."},
            metadata={"status": "failed"}
        )

    # API endpoint and headers
    url = "https://api.bounceban.com/v1/check"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }

    # Correct parameter based on input
    if "@" in query:
        params = { "email": query }
    else:
        params = { "domain": query }

    print(f"Making request to BounceBan with params: {params}")  # Debugging

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        result = response.json()
        print(f"BounceBan API Response: {result}")  # Debugging

        # Format response payload
        check_data = {
            "query": query,
            "domain_type": result.get("domain_type"),
            "username_type": result.get("username_type"),
            "syntax_valid": result.get("syntax_valid"),
            "credits_consumed": result.get("credits_consumed"),
            "credits_remaining": result.get("credits_remaining"),
            "raw": result  # Optional: include raw result for debugging
        }

        return Response(data=check_data, metadata={"status": "success"})

    except requests.exceptions.Timeout:
        return Response(data={"error": "Request timeout"}, metadata={"status": "failed"})

    except requests.exceptions.RequestException as e:
        return Response(data={"error": f"API request failed: {str(e)}"}, metadata={"status": "failed"})

    except Exception as e:
        return Response(data={"error": f"Unexpected error: {str(e)}"}, metadata={"status": "failed"})


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
