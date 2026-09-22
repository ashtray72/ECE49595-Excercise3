import requests

def find_potential_locations(center):
  API_KEY = "AIzaSyDY2K1QOmbspRUx56MdeJM2Mvtjt-pZrYQ"
  url = "https://places.googleapis.com/v1/places:searchNearby" # Using the modern Places API (New) endpoint

  headers = {
      "Content-Type": "application/json",
      "X-Goog-Api-Key": API_KEY,
      # Field masking lets you choose only the data you need to save money
      "X-Goog-FieldMask": "places.displayName,places.location" 
  }

  data = {
      "includedTypes": ["park", 
                        "sports_activity_location", 
                        "sports_complex", 
                        "athletic_field",
                        "community_center"],
      "maxResultCount": 10,
      "locationRestriction": {
          "circle": {
              "center": {
                  "latitude": center[0],
                  "longitude": center[1]
              },
              "radius": 3000.0 # in meters
          }
      }
  }

  response = requests.post(url, headers=headers, json=data)
  return parse_response(response)



def parse_response(response):
  """
  Parses the JSON response and returns dict(displayname : (lat, lon))
  Written by Gemini
  """
  # Check if the request was successful
  if response.status_code != 200:
      print(f"Error: {response.status_code} - {response.text}")
      return {}

  result_json = response.json()
  locations_dict = {}

  try: 
    # Iterate through the places returned in the response
    for place in result_json.get("places", []):
        # Extract the name string from the displayName object
        display_name = place.get("displayName", {}).get("text")
        
        # Extract latitude and longitude
        location = place.get("location", {})
        lat = location.get("latitude")
        lon = location.get("longitude")
        
        # Ensure all required fields exist before adding to dictionary
        if display_name and lat is not None and lon is not None:
            locations_dict[display_name] = (lat, lon)
  except:
     print(f"Error: Incomplete request")
     locations_dict.clear()

  return locations_dict
