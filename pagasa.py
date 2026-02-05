import requests, sys, re, fitz, os, json, time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dataclasses import dataclass #new
# from pathlib import Path
# from io import BytesIO
from notify_alerts import send_alert
import logging
from logging import basicConfig, info, error, debug

@dataclass
class Report:
    report_type: str = "Unknown"
    report_no: int = 0
    date: datetime = None
    # track: str = "Unknown"
    name: str = ""
    wind_speed: str = "Unknown"
    intensity: str = "Unknown"
    url: str = "Unknown"
    place: str = "Ormoc" # Adjust based on liking
    signal_no: int = 0 # from bulletin only
    likelihood :str = "Unknown" # from threat potential only

    @property # Returns label of report i.e. "Advisory 3"
    def label(self):
        return f"{self.report_type.capitalize()} {str(self.report_no)}"

    def __post_init__(self):
        # Capitalizes report types and names
        self.name = self.name.capitalize()
        self.report_type = self.report_type.title()
        # Restricts report type and intensity
        allowed_report_types = ["Advisory", "Bulletin", "Threat Potential"]
        allowed_intensity = ["Low Pressure Area","Tropical Depression", "Tropical Storm", "Severe Tropical Storm", "Typhoon", "Super Typhoon"]
        if self.report_type not in allowed_report_types:
            raise ValueError(f"Invalid Report Type:{self.report_type}.")
        if self.intensity not in allowed_intensity and self.report_type != "Threat Potential":
            raise ValueError(f"Invalid Intensity:{self.intensity}.")
        # Restricts rule that advisories cannot have signal numbers or likelihoods
        if self.report_type == "Advisory" and (self.signal_no != 0 or self.likelihood != "Unknown"):
            raise ValueError("Advisories do not have signal numbers or likelihoods.")
        # Restricts rule that threat potentials cannot have signal numbers
        if self.report_type == "Threat Potential" and self.signal_no != 0:
            raise ValueError("Threat Potentials do not have signal numbers.")
        if self.report_type == "Bulletin" and self.likelihood != "Unknown":
            raise ValueError("Bulletins do not have likelihoods.")

# For logging purposes
log_file = "log.log"
basicConfig(level=logging.DEBUG, filename=log_file, filemode="w",
            format="%(asctime)s - %(levelname)s - %(message)s")
###

start = time.time()
process = time.time()
debug("Checking Website Response")

pagasa_adv = "https://www.pagasa.dost.gov.ph/tropical-cyclone-advisory-iframe"
pagasa_bul = "https://www.pagasa.dost.gov.ph/tropical-cyclone/severe-weather-bulletin"
pagasa_TP = "https://www.pagasa.dost.gov.ph/tropical-cyclone/tc-threat-potential-forecast"

# For trouble shooting
# pagasa_adv_present = "https://web.archive.org/web/20231114132459/https://www.pagasa.dost.gov.ph/tropical-cyclone-advisory-iframe"
# pagasa_bul_present = "https://web.archive.org/web/20251002030048/https://www.pagasa.dost.gov.ph/tropical-cyclone/severe-weather-bulletin"
# pagasa_bul_empty = "https://web.archive.org/web/20251201221931/https://www.pagasa.dost.gov.ph/tropical-cyclone/severe-weather-bulletin"

adv_report = bul_report = tp_report = None

# Returns error if website is unresponsive
try:
    adv_html = requests.get(pagasa_adv, timeout=8).text
    bul_html = requests.get(pagasa_bul, timeout=8).text
    tp_html = requests.get(pagasa_TP, timeout=8).text

    # adv_present = requests.get(pagasa_adv_present, timeout=8).text
    # bul_present = requests.get(pagasa_bul_present, timeout=8).text
    # bul_empty = requests.get(pagasa_bul_empty, timeout=8).text

except Exception:
    error("Error: Site Unresponsive")
    sys.exit()
print("Elapsed:", time.time() - start, "seconds")
start = time.time()
debug("~~~~~~~~~~~~~~~~~~")
#####################################################################################################
## Opens json to be used to compare for new cyclones
json_path = "monitored_cyclones.json"

# Checks for json file, if no file makes blank dict
report_data = {'Bulletin': {},
                'Advisory': {},
                'Threat Potential': {
                    'date':'',
                    'likelihood':''
                    }
                }
if os.path.exists(json_path):
    with open(json_path, "r") as f:
        report_data = json.load(f)

#####################################################################################################

debug("Checking Advisory")
## Check if there is advisory
advisory_stat = True
advisory_link = None
# Extracts PDF link of Advisory
try:
    soup = BeautifulSoup(adv_html, "lxml") #change this
    panel = soup.find('div', class_='panel-body text-center')
    iframe = panel.find_all('iframe')[0]
    advisory_link = iframe["src"]
    info("Advisory found.")
    info(f"Advisory Link: {advisory_link}")
    info(f"Advisory Status: {advisory_stat}")
    print("Elapsed:", time.time() - start, "seconds")
    debug("~~~~~~~~~~~~~~~~~~")

except IndexError:
    info("No Advisory Found")
    debug("~~~~~~~~~~~~~~~~~~")
    advisory_stat = False
except Exception:
    error("Unknown Error in Parsing Advisory")
    advisory_stat = False

## Performs PDF parsing of Advisory if there is one

if advisory_stat:
    debug("Gathering Advisory Data")
    report_no = date = None
    # Converts pdf into text
    response = requests.get(advisory_link)
    pdf = fitz.open(stream=response.content, filetype="pdf")
    text = "".join(page.get_text() for page in pdf)

    # Searches for report number of advisory
    match = re.search(r"ADVISORY\s*NR\.?\s*(\d+)", text)
    if match:
        report_no = int(match.group(1))
    else:
        error("No Report Number")

    # Searches for date-time of report
    match = re.search(r"Issued at\s*(.+)", text)
    if match:
        date_text = match.group(1)
        date = datetime.strptime(date_text, "%I:%M %p, %d %B %Y ")
    else:
        error("No Date Found")
    start2 = time.time()

    ## Temporarily disabled
    # # Searches for track image of report
    # pdf = fitz.open(stream=response.content, filetype="pdf")
    # page = pdf[0]  # page 1
    #
    # # Screenshots page then saves into RAM
    # pic = page.get_pixmap(dpi=300)
    # img_bytes = BytesIO(pic.tobytes("png"))
    # img = PIL.Image.open(img_bytes)
    #
    # # Creates folder for cropped image
    # folder_path = Path("advisory")
    # folder_path.mkdir(parents=True, exist_ok=True)
    #
    # # Crops the screenshot based on bounding box coords
    # x1, y1 = 1183, 790
    # x2, y2 = 2216, 1598
    # cropped = img.crop((x1, y1, x2, y2))
    # track_image_path = folder_path / "atrack_1.png"
    # cropped.save(track_image_path)

    # Searches for cyclone name and intensity
    pattern = r"TROPICAL CYCLONE ADVISORY NR\.\s*\d+\s*\n([^\n]+)"
    match = re.search(pattern, text)
    typhoon_name = typhoon_intensity = "Unknown"
    if match:
        typhoon = match.group(1).split()
        typhoon_name = typhoon.pop().replace('"', '').capitalize()
        typhoon_intensity = " ".join(typhoon).title()
    else:
        error("No Cyclone Name and Intensity Found")

    # Searches for cyclone wind speed
    pattern = r"Maximum\s+sustained\s+winds\s+of\s+(\d+)\s*km/hr?"
    match = re.search(pattern, text)
    if match:
        wind_speed = match.group(1)+ " km/hr"

    # Creates Cyclone object based on gathered data from advisory
    adv_report = Report(
        report_type = 'Advisory',
        report_no = report_no,
        date = date,
        # track = str(track_image_path),
        name = typhoon_name,
        intensity = typhoon_intensity,
        url = str(advisory_link)
    )
    info(f"Report Gathered: {adv_report.label}")
    print("Elapsed:", time.time() - start, "seconds")
    start = time.time()
    debug("~~~~~~~~~~~~~~~~~~")

#####################################################################################################

debug("Checking Bulletin")
## Check if there is bulletin
# FUTURE ME pls simplify this checking part by exploiting html patterns and not using strings
# Suggestion is using the bulldozing method, downloading every single link and checking for patterns
# Parse as pdf since html constantly changes
bulletin_stat = True
tab = row = typhoon_name = typhoon_intensity = None
# Tries to find bulletin using article name and update
article_title = "Tropical Cyclone Bulletin"
article_update = "No Active Tropical Cyclone within the Philippine Area of Responsibility"

# Finds article title
soup = BeautifulSoup(bul_html, "lxml") #change this
page = soup.find('div', class_='row tropical-cyclone-weather-bulletin-page')
header = page.find('div', class_='col-md-12 article-header')
if not header:
    header = page.find('div', class_='article-header') # site uses multiple classes for header

title = header.find('span', style='padding-left:15px;') # site also uses different styles for title
title = header.text.strip() if not title else title.text.strip()

# Finds update in article
panel = page.find('div', class_='panel-body text-center')
update = panel.h3.text if panel else ""

# Checks box for bulletins
if article_title in title and article_update not in update:
    bulletin_stat = True
    info("Bulletin found.")
else:
    info("No Bulletin Found")
    bulletin_stat = False

print("Elapsed:", time.time() - start, "seconds")
start = time.time()
debug("~~~~~~~~~~~~~~~~~~")

## Performs bulletin web parsing if there is one, then appends class data to list
bulletin_list = []

if bulletin_stat:
    debug("Gathering Bulletin Data")
    col_offset = page.find('div', class_='col-md-12 col-lg-10 col-lg-offset-1') # ignores tabs from bulletin archive...at least it should
    tabs = col_offset.find_all('div', class_='tab-content')

    for tab in tabs:
        row = tab.find('div', class_='row')
        typhoon = row.h3.text.split()
        typhoon_name = typhoon.pop().replace('"', '').capitalize()
        typhoon_intensity = " ".join(typhoon).title()

        info(f"Bulletin Storm Name: {typhoon_name}")
        info(f"Bulletin Storm Title: {typhoon_intensity}")
        info(f"Bulletin Status: {bulletin_stat}")

        # Searches for report number
        header = soup.find('div', class_='col-md-12 article-header')
        report_no = re.search(r"#(\d+)", header.text).group(1)

        # Searches for the issue date
        row = tab.find_all('div', class_='row')[1]
        date_text = row.h5.text.strip().removeprefix("Issued at ")
        date = datetime.strptime(date_text, "%I:%M %p, %d %B %Y")

        ## Temporarily disabled
        # # Searches for track image
        # row = tab.find_all('div', class_='row')[2]
        # col = row.find_all('div', class_='col-md-6')[1]
        # image_link = col.img['src']
        #
        # # Create folder then save into folder
        # folder_path = Path("bulletin")
        # folder_path.mkdir(parents=True, exist_ok=True)
        # track_image_path = f"{folder_path}/btrack_1.png"
        #
        # response = requests.get(image_link)
        # with open(track_image_path, "wb") as f:
        #     f.write(response.content)

        # Searches for wind speed

        row = tab.find_all('div', class_='row')[3]
        col = row.find('div', class_='col-md-6')
        panel = col.find_all('div', class_='panel')[2]
        body = panel.find('div', class_='panel-body')
        text = body.p.text.strip().removeprefix("Maximum sustained winds of ")
        text = re.sub(r"(\b\d{1,3})\D.*$", r"\1", text)
        wind_speed = text + " km/hr"
        # Sets url
        bulletin_link = pagasa_bul

        ## Finds signal number of specified place

        signal_no = 0
        tbodies = None

        row = tab.find_all('div', class_='row')[4]
        try:
            table = row.find('table', class_='table text-center table-header')
            tbodies = table.find_all('tbody')
        except AttributeError: pass

        place = "Consolacion"
        if tbodies: # If there is record of signal number
            num = 5 # Records signal number of contents
            loc_list, signal_dict = [], {}

            # Extracts the content in each tbody for the 5 signal numbers, then appends to the dict
            for tbody in tbodies:
                signal_dict[num]= None
                if tbody.ul:
                    ul = tbody.find('ul', style='text-align: left;')
                    li_ups = ul.find_all('li')
                    for li_up in li_ups:
                        if li_up.ul:
                            text = li_up.ul.li.text
                            loc_list.append(text)
                        else:continue
                    signal_dict[num] = loc_list.copy()
                    loc_list.clear()
                else:
                    signal_dict[num] = loc_list
                num -= 1
            reverse_dict = dict(reversed(signal_dict.items()))
            # Checks for the place in each entry and its signal number
            for key, value in reverse_dict.items():
                if value:
                    text = " ".join(value)
                    if place in text:
                        signal_no = key
                else: continue

            # If Consolacion not in list, then check Cebu and return highest signal number
            if not signal_no:
                info(f"{place} does not have a signal number.")
                place = "Cebu"
                for key, value in reverse_dict.items():
                    if value:
                        text = " ".join(value)
                        if place in text:
                            signal_no = key
                    else:
                        continue
                info(f"{place} has signal number {signal_no}")

        # Stores values into a cyclone object
        bul_report = Report(
            report_type = 'Bulletin',
            report_no = report_no,
            date = date,
            # track = str(track_image_path),
            name = typhoon_name,
            intensity = typhoon_intensity,
            url = str(bulletin_link),
            signal_no = signal_no,
            place = place,
            wind_speed = wind_speed
        )
        bulletin_list.append(bul_report)
        info(f"Gathered {bul_report.label}")
    print("Elapsed:", time.time() - start, "seconds")
    start = time.time()
    debug("~~~~~~~~~~~~~~~~~~")

#############################################################################################
# Sets not sending email/notif as default
send_stat = False

## If there are no advisories or bulletins, check threat potential
if not bulletin_stat and not advisory_stat:
    tp_stat = True
    issue_datetime = likelihood = TCThreat_PDF_link = None
    debug("Checking Threat Potential")

    # Extracts PDF link of Typhoon Threat
    try:
        soup = BeautifulSoup(tp_html, "lxml")
        row = soup.find('div', class_='row tc-threat-page')
        col = row.find_all('div', class_='col-md-12')[2]
        TCThreat_PDF_link = col.a['href']
    except Exception:
        info("No TP Report Found")
        tp_stat = False

    # Extracts pdf text
    response = requests.get(TCThreat_PDF_link)
    pdf = fitz.open(stream=response.content, filetype="pdf")
    text = "".join(page.get_text() for page in pdf)

    # Looks for Forecast Date of TC Threat
    match = re.search(r"Date Issued:\s*([A-Za-z0-9, /\-]+)", text)
    if match:
        date = match.group(1)
        issue_datetime = datetime.strptime(date, "%d %B %Y")
        issue_date = datetime.strptime(date, "%d %B %Y").date()  # convert to datetime obj
        end_date = issue_date + timedelta(days=13)
        start_date = issue_date.strftime("%B %d, %Y")
        end_date = end_date.strftime("%B %d, %Y")
        info(f"Forecast Date: From {start_date} to {end_date}")
    else:
        error("No Date Found")

    # Looks for Likelihood of Forecast
    match = re.search(r"TC-THREAT POTENTIAL (?:is|IS)\s+((?:(?:VERY|HIGHLY)\s+)?[A-Z]+)", text)
    if match:
        likelihood = match.group(1)
        info(f"Likelihood: {likelihood} over the next two weeks")
    else:
        error("No Likelihood Found")

    ## Temporarily disabled
    # # Screenshots the entire first page as png
    # pdf = fitz.open(stream=response.content, filetype="pdf")
    # page = pdf[0]  # page 1
    # pic = page.get_pixmap(dpi=300)
    #
    # # Creates folder if needed
    # folder_path = Path("threat potential")
    # folder_path.mkdir(parents=True, exist_ok=True)
    #
    # # Saves image in RAM
    # img_bytes = BytesIO(pic.tobytes("png"))
    # img = PIL.Image.open(img_bytes)
    #
    # # Crops the screenshot based on bounding box coords
    # x1, y1 = 35, 58
    # x2, y2 = 1870, 2238
    # cropped = img.crop((x1, y1, x2, y2))
    # track_image_path = folder_path / "TPtrack_1.png"
    # cropped.save(track_image_path)
    #
    # print("URL: https://www.pagasa.dost.gov.ph/tropical-cyclone/tc-threat-potential-forecast")

    tp_report = Report(
        report_type = "Threat Potential",
        date = issue_datetime,
        likelihood = likelihood,
        # track = str(track_image_path),
        url = pagasa_TP
    )

    # Compare already recorded data from json and incoming data from website
    recorded_date = report_data['Threat Potential']['date']
    recorded_likelihood = report_data['Threat Potential']['likelihood']
    # Cannot save datetime obj in json, so conversion to str is necessary
    incoming_date = tp_report.date.strftime('%Y-%m-%d %H:%M:%S')
    incoming_likelihood = tp_report.likelihood
    # If either is missing OR both are different, update both, then send email
    if not (recorded_date and recorded_likelihood and
            recorded_date == incoming_date and
            recorded_likelihood == incoming_likelihood):
        report_data['Threat Potential']['date'] = incoming_date
        report_data['Threat Potential']['likelihood'] = incoming_likelihood
        info("Sending Threat Potential Report to email")
        send_stat = True
    if send_stat:
        try:
            send_alert(tp_report)
        except Exception:
            error("Unable to connect to Ntfy.")
    print("Elapsed:", time.time() - start, "seconds")
    start = time.time()
    debug("~~~~~~~~~~~~~~~~~~")
##############################################################################################

# 1.Extract data from json
# 2.Check if the names in the recorded reports in json are in the incoming new reports from site
# 3.If not, delete the recorded report with the associated name in the json.
# 4.If yes, then check the report number of the updated report.
# 5.If report number is same, ignore.
# 6.If report number is different, then update report in json, then send update email/notification to me.
# 7.Make new json file.

else: ## Else if either bulletins and advisors are present, check bulletins and advisories
    debug("Checking bulletins/advisories for new updates.")
    ## Skip this for now, can add functionality later
    # if advisory_stat and bulletin_stat:
    #     print("Both are present!")
    #     sys.exit()

    if bulletin_stat:
        debug("Checking bulletins...")
        incoming_bulletins = {}
        recorded_bulletins = report_data['Bulletin']

        for bulletin in bulletin_list: # Makes a dict of all incoming bulletins and their labels
            incoming_bulletins[bulletin.name] = bulletin.label
        # Do the comparison if recorded bulletins exist, else add to the records
        if recorded_bulletins:
            for name in list(recorded_bulletins.keys()):
                # if bulletin name not incoming, then pagasa no longer recording it, thus delete from recorded bulletins
                if name not in incoming_bulletins.keys():
                    info(f"Deleting key for {name} because it is no longer in incoming bulletins")
                    del recorded_bulletins[name]
                else:
                    # If same report number, ignore. If different, then update json and notify user.
                    incoming_label = incoming_bulletins[name]
                    recorded_label = recorded_bulletins[name]
                    if incoming_label == recorded_label:
                        info("No update required for bulletin.")
                        continue
                    else:
                        info("Updating json.")
                        recorded_bulletins[name] = incoming_label
                        info("Sending bulletin to email.")
                        send_stat = True
                        pass
        else:
            for name in list(incoming_bulletins.keys()):
                recorded_bulletins[name] = incoming_bulletins[name]
            info("New update found. Sending bulletin as notification.")
            send_stat = True
        # Sends the notification
        if send_stat:
            for bulletin in bulletin_list:
                try:
                    send_alert(bulletin)
                except Exception:
                    error("Unable to connect to Ntfy.")

    elif advisory_stat:
        debug("Checking advisories...")
    # Since idk what format website follows for multiple advisories, assume only one advisory is recorded
    # FUTURE ME update this to include case of multiple advisories
    # Suggestion is using the bulldozing method, downloading every single link and checking for patterns
        incoming_advisories = {}
        recorded_advisories = report_data['Advisory']
        incoming_advisories[adv_report.name] = adv_report.label
        # Do the comparison if recorded advisories exist
        if recorded_advisories:
            for name in list(recorded_advisories.keys()):
                # if advisory name not incoming, then pagasa no longer recording it, thus delete from recorded advisories
                if name not in incoming_advisories.keys():
                    info(f"Deleting key for {name} since it is no longer in incoming advisories")
                    del recorded_advisories[name]
                else:
                    # If same report number, ignore. If different, then update json and notify user.
                    incoming_label = incoming_advisories[name]
                    recorded_label = recorded_advisories[name]
                    if incoming_label == recorded_label:
                        info("No update required for advisory.")
                        continue
                    else:
                        info("Updating json.")
                        recorded_advisories[name] = incoming_label
                        info("New update found. Sending advisory as notification.")
                        send_stat = True
                        pass
        else: # else if no records, add incoming advisory to the record
            for name in list(incoming_advisories.keys()):
                recorded_advisories[name] = incoming_advisories[name]
            send_stat = True
        if send_stat:
            try:
                send_alert(adv_report)
            except Exception:
                error("Unable to connect to Ntfy.")
    info(report_data)

json_string = json.dumps(report_data, indent=4)
debug(json_string)
with open(json_path, 'w') as f:
    json.dump(report_data, f, indent=4)

debug("Entire Process Executed")
print("Elapsed:", time.time() - process, "seconds")
