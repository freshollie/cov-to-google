import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
import pytz

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

    # Parse the datetime info
    for event in parsed_data:
        if "start" in event:
            event["start"] = list(event["start"])
            event["start"][1] += 1
            event["start"].append(0)
            event["start"] = datetime(*event["start"])
            event["start"] = pytz.timezone("Europe/London").localize(event["start"])
        
        if "end" in event:
            event["end"] = list(event["end"])
            event["end"][1] += 1
            event["end"].append(0)
            event["end"] = datetime(*event["end"])
            event["end"] = pytz.timezone("Europe/London").localize(event["end"])

    return parsed_data

def get_timetable_data(url):
    return requests.get(url).text

def create_google_event(event):
    new_event = event.copy()

    if not new_event:
        return new_event

    # Make the event the correct format
    new_event["summary"] = event["moduleDesc"] + " - " + event["title"]
    new_event["description"] = event["lecturer"] + " - " + event["room"]

    new_event["end"] = {"dateTime": str(event["end"].isoformat()), "timeZone": "Europe/London"}
    new_event["start"] = {"dateTime": str(event["start"].isoformat()), "timeZone": "Europe/London"}
    
    new_event["reminders"] = {'useDefault': False,
                              'overrides': [{'method': 'popup', 'minutes': 30}]}
    return new_event

# If modifying these scopes, delete the file token.json.
SCOPES = 'https://www.googleapis.com/auth/calendar'

def main():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """

    type_to_color = {}
    color_queue = list(range(0, 12))
    
    store = file.Storage('token.json')
    creds = store.get()

    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
        creds = tools.run_flow(flow, store)
    service = build('calendar', 'v3', http=creds.authorize(Http()))

    cov_events = parse_events(get_timetable_data(URL))

    for event in cov_events:
        new_event = create_google_event(event)
        
        color_type = new_event["mainColor"]
        
        if color_type in type_to_color:
            colorId = type_to_color[color_type]
        else:
            colorId = color_queue.pop(0)
            color_queue.append(colorId)
            type_to_color[color_type] = colorId

        new_event["colorId"] = colorId

        service.events().insert(body=new_event, calendarId='primary').execute()

main()
