import calendar
import datetime
import json
import random
from datetime import datetime
import pandas as pd
import requests
from requests.structures import CaseInsensitiveDict


def randomDate(year, month):
    day_count = calendar.monthrange(year, month)[1]
    t = random.choice(pd.date_range(f"{year}-{month}-01", f"{year}-{month}-{day_count}", freq='D'))
    return randomDate(year, month) if t.dayofweek == 5 or t.dayofweek == 6 else t


def get_day_and_doc(preferred_days, preferred_docs, schedule, is_new):
    preferred_day = ""
    preferred_doc = ""
    if len(preferred_days) == 0:
        preferred_day = randomDate(2021, 11).strftime("%Y-%m-%dT%H:%M:%SZ")
        if len(preferred_docs) == 0:
            preferred_doc = random.randint(1, 3)
        else:
            preferred_doc = preferred_docs[0]
    for day in preferred_days:
        if is_new:
            doc_available = available_new(day, preferred_docs, schedule)
        else:
            doc_available = available_doctor(day, preferred_docs, schedule)
        if len(doc_available) > 0:
            preferred_doc = doc_available[0]
            preferred_day = day
            break
    return preferred_day, preferred_doc


def schedule_new_patient(preferred_day, preferred_doc, person_id, schedule):
    date = preferred_day.split("T")
    appt_date = date[0] + "T15:00:00.000Z"
    for appt in schedule:
        if appt["appointmentTime"] == date[0] + "T15:00:00.000Z" and appt["doctorId"] == preferred_doc:
            appt_date = date[0] + "T16:00:00.000Z"
    return json.dumps({
        "doctorId": preferred_doc,
        "personId": person_id,
        "appointmentTime": appt_date,
        "isNewPatientAppointment": True,
        "requestId": 0})


def schedule_patient(preferred_day, preferred_doc, person_id, schedule):
    date = preferred_day.split("T")
    appt_date = date[0]
    available_hours = ["T08:00:00.000Z", "T09:00:00.000Z", "T10:00:00.000Z", "T11:00:00.000Z", "T12:00:00.000Z",
                       "T13:00:00.000Z", "T14:00:00.000Z", "T15:00:00.000Z", "T16:00:00.000Z"]
    for appt in schedule:
        temp = appt["appointmentTime"].split("T")
        if temp[0] == appt_date:
            if temp[1] in available_hours:
                available_hours.remove(temp[1])
    return json.dumps({
        "doctorId": preferred_doc,
        "personId": person_id,
        "appointmentTime": appt_date + available_hours[0],
        "isNewPatientAppointment": False,
        "requestId": 0})


def available_new(preferred_day, preferred_doc, schedule):
    date = preferred_day.split("T")
    appt_date = date[0] + "T15:00:00.000Z"
    three = True
    for doc in preferred_doc:
        for appt in schedule:
            if appt["appointmentTime"] == appt_date and appt["doctorId"] == doc:
                three = False
                break
        if not three:
            appt_date = date[0] + "T16:00:00.000Z"
            for appt in schedule:
                if appt["appointmentTime"] == appt_date and appt["doctorId"] == doc:
                    preferred_doc.remove(doc)
    return preferred_doc


def available_doctor(preferred_day, preferred_doc, schedule):
    for appt in schedule:
        if appt["appointmentTime"] == preferred_day and appt["doctorId"] in preferred_doc:
            preferred_doc.remove(appt["doctorId"])
    return preferred_doc


def main():
    # request initial schedule
    # get schedule requests from the queue
    headers = CaseInsensitiveDict()
    access_token = "c5ec4da0-c9e7-4e2d-b890-b38e4c1d2cf1"
    headers['token'] = f"{access_token}"
    start = requests.post(
        "http://scheduling-interview-2021-265534043.us-west-2.elb.amazonaws.com/api/Scheduling/Start"
        "?token=c5ec4da0-c9e7-4e2d-b890-b38e4c1d2cf1", headers=headers)
    print(start.status_code)
    schedule_url = "http://scheduling-interview-2021-265534043.us-west-2.elb.amazonaws.com/api/Scheduling/Schedule" \
                   "?token=c5ec4da0-c9e7-4e2d-b890-b38e4c1d2cf1"
    response = requests.get(schedule_url, headers=headers)
    schedule = json.loads(response.text)
    next_request = requests.get("http://scheduling-interview-2021-265534043.us-west-2.elb.amazonaws.com/api"
                                "/Scheduling/AppointmentRequest?token=c5ec4da0-c9e7-4e2d-b890-b38e4c1d2cf1",
                                headers=headers)
    while next_request.status_code != "204":
        """Scheduling Constraints:
    - appts can only be scheduled on the hour
    - 8 am - 4 pm UTC
    - only weekdays from Nov-Dec 2021
    - holidays are okay
    - only one appt scheduled per dr per hour
    - for one patient, all appts have to be at least a week apart
    - appts for new patients are only scheduled at 3 and 4 pm"""
        request_json = json.loads(next_request.text)
        preferred_days = request_json["preferredDays"]
        for time in preferred_days:
            time = datetime.strptime(time, "%Y-%m-%dT%H:%M:%SZ")
            if not 0 <= time.weekday() <= 4:
                preferred_days.remove(time)
            if not datetime(2021, 11, 1) <= time <= datetime(2021, 12, 31):
                preferred_days.remove(time)
        if request_json["isNew"]:
            preferred_day, preferred_doc = get_day_and_doc(preferred_days, request_json["preferredDocs"], schedule,
                                                           True)
            request = schedule_new_patient(preferred_day, preferred_doc, request_json["personId"], schedule)
            request = json.loads(request)
            schedule.append(request)

        else:
            for appt in schedule:
                if appt["personId"] == request_json["personId"]:
                    if appt["appointmentTime"] in preferred_days:
                        preferred_days.remove(appt["appointmentTime"])
                        continue
                    for day in preferred_days:
                        str_day = day
                        day = datetime.strptime(day, "%Y-%m-%dT%H:%M:%SZ")
                        try:
                            appt_day = datetime.strptime(appt["appointmentTime"], "%Y-%m-%dT%H:%M:%S.%fZ")
                        except:
                            appt_day = datetime.strptime(appt["appointmentTime"], "%Y-%m-%dT%H:%M:%SZ")
                        if not (day - appt_day).days >= 7 or (appt_day - day).days >= 7:
                            preferred_days.remove(str_day)
                            if len(preferred_days) == 0:
                                print("None of your preferred days are available!")
            preferred_day, preferred_doc = get_day_and_doc(preferred_days, request_json["preferredDocs"], schedule,
                                                           False)
            request = schedule_patient(preferred_day, preferred_doc, request_json["personId"], schedule)
            request = json.loads(request)
            schedule.append(request)
        # send appt request here --> check for success or failure
        try:
            response = requests.post(
                "http://scheduling-interview-2021-265534043.us-west-2.elb.amazonaws.com/api/Scheduling/Schedule?token"
                "=c5ec4da0-c9e7-4e2d-b890-b38e4c1d2cf1",
                headers=headers, json=request)
            print(response.reason)
            print(
                "Scheduled patient " + str(request["personId"]) + " with doctor " + str(request["doctorId"]) + " at " +
                request["appointmentTime"])
        except:
            print(response.status_code)
            print(response.reason)
        next_request = requests.get(
            "http://scheduling-interview-2021-265534043.us-west-2.elb.amazonaws.com/api/Scheduling/AppointmentRequest"
            "?token=c5ec4da0-c9e7-4e2d-b890-b38e4c1d2cf1",
            headers=headers)
    return "New Schedule has been updated!"


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()
