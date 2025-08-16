import requests
from fastapi import FastAPI, Cookie, Response

# Copy the session-token value from browser dev tools
session_token = "eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..3FR5G8uFllzz9qWq.cgPXaCfGO-D5hqJM8ppMp7tPx_JWkc6U1sESDUSsplfXKMB4EPrjM-JrM6aurwToq419QUXsOgI6Re0Ro6oxlxZ5RAOvwB7EuowBRWZC_eKdVJyr0cmFDwYtw3w_sdi626uG7T7FAPeBtROByhoVk6ZOfv8yzpUHEbDyDRZhsSCfucqE0EhI834AquAxGjnqZFCJ_WWxq5uaAvad3IQOMiuHUGDNMZljLldGJaWf_BJhg7MlCGyN.cQcItOQZx_Yc_F6zKqIHpQ"

upload_image_url = "https://forestmarket.net/api/trpc/upload.getPresignedUrl?batch=1"

# Method 1: Using cookies parameter
cookies = {"__Secure-next-auth.session-token": session_token}

def get_presigned_url(file_name: str, file_type: str, session_token: str):
    """Get presigned URL from the tRPC API"""
    
    # Replace with the actual tRPC endpoint URL from network tab
    url = "https://forestmarket.net/api/trpc/upload.getPresignedUrl?batch=1"
    
    payload = {
        "0": {
            "json": {
                "fileName": file_name,
                "fileType": file_type
            }
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "trpc-accept": "application/json",
    }
    
    cookies = {
        "__Secure-next-auth.session-token": session_token
    }
    
    response = requests.post(url, json=payload, headers=headers, cookies=cookies)
    
    if response.status_code == 200:
        result = response.json()
        return result[0]["result"]["data"]["json"]
    else:
        raise Exception(f"Failed to get presigned URL: {response.status_code} - {response.text}")

# Test it
presigned_data = get_presigned_url("/home/haorui/Python/DarwinG-Upload/8fdc43456b4eaa80a97144f572734d15.png", "image/png", session_token)
print(f"Presigned URL: {presigned_data['presignedUrl']}")
print(f"Object URL: {presigned_data['objectUrl']}")
print(f"Key: {presigned_data['key']}")
