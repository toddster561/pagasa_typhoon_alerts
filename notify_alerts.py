import requests
from datetime import timedelta

NTFY_TOPIC = "pagasa-cyclone-alerts-561"

def send_alert(report):
    title = "Report"
    tags = "rotating_light"
    start_date = end_date = "Unknown"
    message =""

    # Choose priority and change message based on threat level
    if "Bulletin" in report.report_type:
        tags = "cyclone"
        title = f"{report.name} Bulletin {report.report_no}"
        message = (
            f"Intensity: {report.intensity}"
            f"\nSignal Number {report.signal_no} in {report.place}"
            f"\nIssue Date: {report.date}"
            f"\nWind Speed: {report.wind_speed}"
        ).strip()
    elif "Advisory" in report.report_type:
        tags = "cloud_with_rain"
        title = f"{report.name} Advisory {report.report_no}"
        message = (
            f"Intensity: {report.intensity}"
            f"\nIssue Date: {report.date}"
            f"\nWind Speed: {report.wind_speed}"
        ).strip()
    elif "Threat Potential" in report.report_type:
        tags = "red_circle"
        title = "Typhoon Potential Report"
        issue_date = report.date.date()
        end_date = issue_date + timedelta(days=13)
        start_date = issue_date.strftime("%B %d, %Y")
        end_date = end_date.strftime("%B %d, %Y")
        message = (
        f"Chance of typhoon is {report.likelihood}"
        f"\nFrom {start_date} to {end_date}"
        ).strip()

    response = requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode('utf-8'),
        headers={
            "Title": title,
            "Priority": "default",
            "Tags": tags,
            "Actions": f"view, View Details, {report.url}"
        }
    )
    return response.status_code == 200
