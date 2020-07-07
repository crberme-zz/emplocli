from argparse import ArgumentParser
from xmlrpc import client
from xmlrpc.client import ProtocolError
import logging
import json
from os import path, getcwd
from shutil import move

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
    

class EmployeeClient:
    def __init__(self, url, db, username, password):
        self.url = url
        self.db = db
        self.username = username
        self.password = password

        self.common = client.ServerProxy('{}/xmlrpc/2/common'.format(self.url))
        self.models = client.ServerProxy('{}/xmlrpc/2/object'.format(self.url))

        self.id = None
        self.attendance_state = None

    def login(self):
        self.uid = self.common.authenticate(self.db, self.username, self.password, {})
        if not self.uid:
            return False
        else:
            return True

    def get_reasons(self):
        return self.models.execute_kw(self.db, self.uid, self.password, 'hr.attendance.reason', 'search_read', [[]], {"fields": ["name"]})

    def register_attendance(self):
        return self.models.execute_kw(self.db, self.uid, self.password, 'hr.employee', 'attendance_manual', [self.id, False])

    def register_attendance_reason(self, attendance_id, reason):
        # [6, False, [IDs]] deletes the current IDs and inserts the provided one(s) in a single operation
        return self.models.execute_kw(self.db, self.uid, self.password, 'hr.attendance', 'write', [[attendance_id], {'attendance_reason_ids': [[6, False, [reason]]]}])

    def check_in(self):
        attendance_state = self.get_attendance_state()
        if attendance_state == "checked_in":
            logging.info("User already checked in.")
        else:
            try:
                action = self.register_attendance()
                logging.info("Checked in.")
            except ProtocolError as err:
                logging.error(err.errmsg)

    def check_out(self, reason=None):
        attendance_state = self.get_attendance_state()
        if attendance_state == "checked_out":
            logging.info("User not checked in.")
        else:
            try:
                response = self.register_attendance()
                logging.info("Checked out.")
            except ProtocolError as err:
                logging.error(err.errmsg)
                return

            if reason:
                if any(reasons.get("id") == reason for reasons in self.get_reasons()):
                    try:
                        self.register_attendance_reason(response.get("action").get("attendance").get("id"), reason)
                        logging.info("Attendance reason set.")
                    except ProtocolError as err:
                        logging.error(err.errmsg)
                        return
                else:
                    logging.error("Unknown reason ID \"%s\", please use the --list-reasons or -R flags to get a list of available reason IDs.", args.reason)


    def get_attendance_state(self):
        response = self.models.execute_kw(self.db, self.uid, self.password, 'hr.employee', 'search_read', [[['user_id', '=', self.uid]]], {'fields': ['attendance_state']})
        for response_item in response:
            if self.id:
                logging.warn("Overriding ID with value \"%i\", original value was \"%i\"", response_item.get("id"), self.id)

            self.id = response_item.get("id")
            
            if self.attendance_state:
                logging.warn("Overriding attendance state with value \"%s\", original value was \"%s\"", response_item.get("attendance_state"), self.attendance_state)

            attendance_state = response_item.get("attendance_state")

        return attendance_state


if __name__ == "__main__":
    logging.basicConfig(filename=__file__[:__file__.rfind(".")] + ".log", level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")

    # Initialize variables
    args = read_arguments()
    config = read_config_file()
    client = EmployeeClient(config["url"], config["db"], config["username"], config["password"])
    
    # Perform action
    if client.login():
        if args.list_reasons:
            reasons = client.get_reasons()

            print("Available reason IDs:")
            print("ID\tName")
            print(("=" * max(len(str(reason["id"])) for reason in reasons)) + "\t" + ("=" * max(len(reason["name"]) for reason in reasons)))
            for reason in reasons:
                print(str(reason.get("id")) + "\t" + reason.get("name"))
        else:
            if args.check == 1:
                client.check_in()
            elif args.check == 2:
                if args.reason:
                    client.check_out(int(args.reason))
                else:
                    client.check_out()
    else:
        logging.error("Login failed.")