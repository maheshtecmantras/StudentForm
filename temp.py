import requests

# Replace this with your actual Apps Script deployment URL
url = "https://script.google.com/macros/s/AKfycbz3UM6Zp50zXKO1d7S64n5F2pCw8q7tlB3bx-K-mk6_3Az_y9A-dTs-Nm0xTymdE5YltA/exec"
response = requests.post(url)
print(response.text)  # Will print the form edit URL
