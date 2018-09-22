import requests
from bs4 import BeautifulSoup
from datetime import datetime
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools

URL = open("timetableurl").read().strip()

def parse_events(page_data):
    soup = BeautifulSoup(page_data, features="html.parser")

    source = ""
    for script in soup.head.findAll("script", {"type": "text/javascript"}):
        if not script.has_attr("src"):
            source = script.text
            break
    
    events_data = source.split("events:")[1].split("]")[0] +"]"

    # Replace date objects with tuples, easier to parse
    events_data = events_data.replace("new Date", "")

    cleaned_data = ""

    # Remove comments, properties to keys
    for line in events_data.split("\n"):
        comment_pos = line.find("//")
        if comment_pos != -1:
            line = line[:comment_pos]
        

        if ":" in line:
            line_values = line.split(":")
            line = "'" + line_values[0] + "': " + line_values[1] 
 
        cleaned_data += line + "\n"   

    parsed_data = eval(cleaned_data)

    for event in parsed_data:
        if "start" in event:
            event["start"] = list(event["start"])
            event["start"][1] += 1
            event["start"] = datetime(*event["start"])
        
        if "end" in event:
            event["end"] = list(event["end"])
            event["end"][1] += 1
            event["end"] = datetime(*event["end"])

    return parsed_data

# If modifying these scopes, delete the file token.json.
SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'

def main():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    store = file.Storage('token.json')
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
        creds = tools.run_flow(flow, store)
    service = build('calendar', 'v3', http=creds.authorize(Http()))

    # Call the Calendar API
    now = datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    print('Getting the upcoming 10 events')
    events_result = service.events().list(calendarId='primary', timeMin=now,
                                        maxResults=10, singleEvents=True,
                                        orderBy='startTime').execute()
    events = events_result.get('items', [])

    if not events:
        print('No upcoming events found.')
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(start, event['summary'])
    
    new_event = parse_events(requests.get(URL).text)[0]
    new_event["title"] += " - " + new_event["lecturer"]
    new_event["description"] = new_event[""] 
    print(new_event)
    service.events().insert(body=new_event).execute()

main()
