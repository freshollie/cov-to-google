import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
import pytz

# We don't store this url in the source, as it is sensitive
URL = open("timetableurl").read().strip()

def parse_events(events_data):
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

    # Parse the event, as if it were a dict
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


def get_events_data(url):
    page_data = requests.get(url).text

    soup = BeautifulSoup(page_data, features="html.parser")

    source = ""
    for script in soup.head.findAll("script", {"type": "text/javascript"}):
        if not script.has_attr("src"):
            source = script.text
            break
    
    events_data = source.split("events:")[1].split("]")[0] +"]"

    return events_data


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


# Read and write access
SCOPES = "https://www.googleapis.com/auth/calendar"

def get_calendar_service():
    '''
    Connect to the google calendar service, and return the
    service object
    '''

    store = file.Storage("token.json")
    creds = store.get()

    # Run prompt to get the google credentials
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets("redentials.json", SCOPES)
        creds = tools.run_flow(flow, store)

    return build("calendar", "v3", http=creds.authorize(Http()))


def execute_batch(service, commands):
    batch = service.new_batch_http_request()
    batch_count = 0

    for command in commands:
        batch.add(command)
        batch_count += 1
        
        if batch_count > 999:
            batch.execute()

            batch = service.new_batch_http_request()
            batch_count = 0
    
    if batch_count > 0:
        batch.execute()


def main():
    type_to_color = {}
    # A queue of colors, where a color is removed when
    # when an event we have not seen before exists
    color_queue = list(range(0, 12, 3))

    service = get_calendar_service()

    # Get a list of all events in the future
    results = service.events().list(timeMin=datetime.now().isoformat() + 'Z', calendarId='primary').execute()
    future_events = results.get("items", [])

    cov_events = parse_events(get_events_data(URL))
    new_events = []

    new_summaries = set()

    for event in cov_events:
        if not event:
            continue

        new_event = create_google_event(event)

        color_type = new_event["mainColor"]
        
        if color_type in type_to_color:
            colorId = type_to_color[color_type]
        else:
            colorId = color_queue.pop(0)
            color_queue.append(colorId)
            type_to_color[color_type] = colorId

        new_event["colorId"] = colorId

        new_events.append(new_event)  
        new_summaries.add(new_event["summary"])  

    # Make sure we remove old events so as not to create duplicates
    if not future_events:
        print('No existing events found')
    else:
        deletes = []
        for existing_event in future_events:
            if "summary" in existing_event and existing_event["summary"] in new_summaries:
                deletes.append(service.events()
                                      .delete(calendarId='primary', 
                                              eventId=existing_event['id']))


        print(f'Removing {len(deletes)} existing events')
        execute_batch(service, deletes)

    inserts = []
    for new_event in new_events:
        inserts.append(service.events()
                              .insert(body=new_event, 
                                      calendarId='primary'))
    print(f"Inserting {len(inserts)} new events")
    execute_batch(service, inserts)
                    


if __name__ == "__main__":
    main()
