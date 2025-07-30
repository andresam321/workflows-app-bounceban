from workflows_cdk import Request, Response
from flask import request as flask_request
from main import router
import requests
import os
import time
def extract_api_key(api_connection: dict) -> str:
    if not api_connection:
        return None
    return api_connection.get("connection_data", {}).get("value", {}).get("api_key_bearer")

def submit_bulk_verification(emails: list, task_name: str, api_key: str) -> dict:
    """Submit emails for bulk verification"""
    url = "https://api.bounceban.com/v1/verify/bulk"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "name": task_name,
        "emails": emails
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()

def check_bulk_status(task_id: str, api_key: str) -> dict:
    """Check the status of a bulk verification task"""
    url = "https://api.bounceban.com/v1/verify/bulk/status"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    params = {"id": task_id}
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def get_bulk_results(task_id: str, api_key: str, offset: int = 0, limit: int = 1000, filter_status: str = "all") -> dict:
    """Retrieve bulk verification results"""
    url = "https://api.bounceban.com/v1/verify/bulk/dump"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    params = {
        "id": task_id,
        "offset": offset,
        "limit": limit
    }
    if filter_status != "all":
        params["filter"] = filter_status
    
    response = requests.get(url, headers=headers, params=params, timeout=60)
    response.raise_for_status()
    return response.json()

@router.route("/execute", methods=["POST", "GET"])
def execute():
  
    request = Request(flask_request)
    data = request.data
    api_key = extract_api_key(data.get("api_connection"))
    if not api_key:
        return Response(
            data={"error": "API key is required"},
            metadata={"status": "failed"}
        )
    # data = flask_request.get_json(force=True)
    # api_key = os.getenv("BOUNCEBAN_API_KEY")

    task_id = data.get("task_id")
    

    def poll_until_complete(task_id, task_name="Bulk Verification Task"):
        offset = data.get("offset", 0)
        limit = data.get("limit", 1000)
        filter_status = data.get("filter_status", "all")
        start_time = time.time()
        max_wait_time = 60  # seconds
        poll_interval = 5   # seconds

        while True:
            status_result = check_bulk_status(task_id, api_key)
            task_status = status_result.get("status", "").strip().lower()
            elapsed_time = time.time() - start_time
            print(f"[{elapsed_time:.1f}s] Task {task_id} status: {task_status}")

            status_data = {
                "task_id": task_id,
                "task_name": task_name,
                "status": status_result.get("status"),
                "count_total": status_result.get("count_total", 0),
                "count_checked": status_result.get("count_checked", 0),
                "count_remaining": status_result.get("count_remaining", 0),
                "progress_percentage": status_result.get("progress_percentage", 0),
                "verification_started_at": status_result.get("verification_started_at"),
                "verification_ended_at": status_result.get("verification_ended_at"),
                "estimated_time_remaining": status_result.get("estimated_time_remaining"),
                "created_at": status_result.get("created_at"),
                "updated_at": status_result.get("updated_at")
            }

            if task_status in ["completed", "complete", "finished"]:
                if offset < 0: offset = 0
                if limit < 1 or limit > 10000: limit = 1000
                if filter_status not in ["all", "deliverable", "undeliverable", "risky", "unknown"]:
                    filter_status = "all"

                results = get_bulk_results(task_id, api_key, offset, limit, filter_status)
                print(f"Retrieved {len(results.get('items', []))} results for task {task_id}")

                processed_results = []
                for email_result in results.get("items", []):
                    processed_results.append({
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
                        "verified_at": email_result.get("verify_at")
                    })

                return Response(
                    data={
                        **status_data,
                        "returned_results": len(processed_results),
                        "offset": offset,
                        "limit": limit,
                        "filter_status": filter_status,
                        "results": processed_results
                    },
                    metadata={"status": "success"}
                )

            elif task_status in ["failed", "error", "cancelled"]:
                return Response(data=status_data, metadata={"status": "failed"})

            if elapsed_time >= max_wait_time:
                print(f"Timeout reached after {elapsed_time:.1f}s - task still processing")
                return Response(data=status_data, metadata={"status": "still processing"})

            time.sleep(poll_interval)

    try:
        if task_id:
            print(f"Polling existing task ID: {task_id}")
            return poll_until_complete(task_id)

        # Mode 1: Submit new bulk verification
        emails_raw = data.get("emails", "")

        if isinstance(emails_raw, str):
            emails = [email.strip() for email in emails_raw.splitlines() if email.strip()]
        elif isinstance(emails_raw, list):
            emails = [email.strip() for email in emails_raw if email and email.strip()]
        else:
            return Response(
                data={"error": "Emails must be provided as a string (one per line) or a list"},
                metadata={"status": "failed"}
            )

        if not emails:
            return Response(
                data={"error": "At least one email address is required"},
                metadata={"status": "failed"}
            )

        if len(emails) > 500000:
            return Response(
                data={"error": "Maximum 500,000 emails allowed per bulk task"},
                metadata={"status": "failed"}
            )

        task_name = data.get("task_name", "Bulk Verification Task")
        print(f"Submitting {len(emails)} emails for bulk verification...")

        result = submit_bulk_verification(emails, task_name, api_key)
        task_id = result.get("id")

        print(f"Task created: {task_id}, polling for completion...")
        return poll_until_complete(task_id, task_name)

    except requests.exceptions.Timeout:
        return Response(data={"error": "Request timeout"}, metadata={"status": "failed"})

    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_details = e.response.json()
                error_msg = f"API error: {error_details.get('message', str(e))}"
            except:
                pass
        return Response(data={"error": error_msg}, metadata={"status": "failed"})

    except Exception as e:
        return Response(data={"error": f"Unexpected error: {str(e)}"}, metadata={"status": "failed"})

# @router.route("/content", methods=["GET", "POST"])
# def content():
#     """
#     This is the function that goes and fetches the necessary data to populate the possible choices in dynamic form fields.
#     For example, if you have a module to delete a contact, you would need to fetch the list of contacts to populate the dropdown
#     and give the user the choice of which contact to delete.

#     An action's form may have multiple dynamic form fields, each with their own possible choices. Because of this, in the /content route,
#     you will receive a list of content_object_names, which are the identifiers of the dynamic form fields. A /content route may be called for one or more content_object_names.

#     Every data object takes the shape of:
#     {
#         "value": "value",
#         "label": "label"
#     }
    
#     Args:
#         data:
#             form_data:
#                 form_field_name_1: value1
#                 form_field_name_2: value2
#             content_object_names:
#                 [
#                     {   "id": "content_object_name_1"   }
#                 ]
#         credentials:
#             connection_data:
#                 value: (actual value of the connection)

#     Return:
#         {
#             "content_objects": [
#                 {
#                     "content_object_name": "content_object_name_1",
#                     "data": [{"value": "value1", "label": "label1"}]
#                 },
#                 ...
#             ]
#         }
#     """
#     request = Request(flask_request)

#     data = request.data

#     form_data = data.get("form_data", {})
#     content_object_names = data.get("content_object_names", [])
    
#     # Extract content object names from objects if needed
#     if isinstance(content_object_names, list) and content_object_names and isinstance(content_object_names[0], dict):
#         content_object_names = [obj.get("id") for obj in content_object_names if "id" in obj]

#     content_objects = [] # this is the list of content objects that will be returned to the frontend

#     for content_object_name in content_object_names:
#         if content_object_name == "requested_content_object_1":
#             # logic here
#             data = [
#                 {"value": "value1", "label": "label1"},
#                 {"value": "value2", "label": "label2"}
#             ]
#             content_objects.append({
#                     "content_object_name": "requested_content_object_1",
#                     "data": data
#                 })
#         elif content_object_name == "requested_content_object_2":
#             # logic here
#             data = [
#                 {"value": "value1", "label": "label1"},
#                 {"value": "value2", "label": "label2"}
#             ]
#             content_objects.append({
#                     "content_object_name": "requested_content_object_2",
#                     "data": data
#                 })
    
#     return Response(data={"content_objects": content_objects})
