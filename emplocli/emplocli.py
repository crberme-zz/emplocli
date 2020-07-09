from argparse import ArgumentParser
from xmlrpc import client
from xmlrpc.client import ProtocolError
import logging
import json
from os import path, getcwd
from shutil import move
from utils.ApiClient import ApiClient

def read_arguments():
    parser = ArgumentParser(description="Register attendances on an Odoo instance.")
    args_group = parser.add_mutually_exclusive_group()
    args_group.add_argument("--check-in", "-i", dest="check", action="store_const", const=1, help="Register a check in.")
    args_group.add_argument("--check-out", "-o", dest="check", action="store_const", const=2, help="Register a check out.")
    parser.add_argument("--reason", "-r", help="Specify the attendance reason ID for check out.")
    parser.add_argument("--list-reasons", "-R", action="store_true", help="List the available reason ID with a brief description.")
    return parser.parse_args()

def read_config_file():
    try:
        return json.load(open(path.join(path.dirname(__file__), "config.json")))
    except OSError:
        try:
            # Move old config file to module path
            config = json.load(open("config.json"))

            move(path.join(getcwd(), "config.json"), path.join(path.dirname(__file__), "config.json"))
            logging.info("Moved config file to module path.")
            return config
        except ImportError:
            with open(path.join(path.dirname(__file__), "config.json"), "w") as file:
                file.write(json.dumps({
                    "url": "",
                    "db": "",
                    "username": "",
                    "password": ""
                }))
            logging.error("No config found. Please fill the created config.json file and try again.")
            raise ValueError("Invalid config.")

if __name__ == "__main__":
    logging.basicConfig(filename=__file__[:__file__.rfind(".")] + ".log", level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

    # Initialize variables
    args = read_arguments()
    config = read_config_file()
    url = config["url"]
    db = config["db"]
    username = config["username"]
    password = config["password"]
    api = ApiClient(url)
    
    # Perform action
    uid = api.authenticate(db, username, password)
    if not uid:
        logging.error("Login failed.")
    else:
        if args.list_reasons:
            reasons = api.search_read(db, uid, password, "hr.attendance.reason", "name")
            
            print("Available reason IDs:")
            print("ID\tName")
            print(("=" * max(len(str(reason["id"])) for reason in reasons)) + "\t" + ("=" * max(len(reason["name"]) for reason in reasons)))
            for reason in reasons:
                print(str(reason.get("id")) + "\t" + reason.get("name"))
        else:
            response = api.search_read(db, uid, password, "hr.employee", "attendance_state", {"field_name": "user_id", "operator": "=", "value": uid})[0]
            attendance_state = response.get("attendance_state")
            employee_id = response.get("id")

            if args.check == 1:
                if attendance_state == "checked_in":
                    logging.info("User already checked in.")
                else:
                    response = api.attendance_manual(db, uid, password, employee_id)
                    logging.info("Checked in.")
            elif args.check == 2:
                if attendance_state == "checked_out":
                    logging.info("User not checked in.")
                else:
                    response = api.attendance_manual(db, uid, password, employee_id)
                    logging.info("Checked out.")

                    if args.reason:
                        reason = int(args.reason)
                        if any(reasons.get("id") == reason for reasons in api.search_read(db, uid, password, "hr.attendance.reason", "name")):
                            attendance_id = response.get("action").get("attendance").get("id")
                            # [6, False, [IDs]] deletes the current IDs and inserts the provided one(s) in a single operation
                            response = api.write(db, uid, password, 'hr.attendance', attendance_id, 'attendance_reason_ids', [[6, False, [reason]]])
                            logging.info("Attendance reason set.")
                        else:
                            logging.error("Unknown reason ID \"%s\", please use the --list-reasons or -R flags to get a list of available reason IDs.", args.reason)