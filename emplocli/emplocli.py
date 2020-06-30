from argparse import ArgumentParser
from data import url, db, username, password
from xmlrpc import client

# Initialize the argument parser
parser = ArgumentParser(description="Register attendances on an Odoo instance.")
args_group = parser.add_mutually_exclusive_group()
args_group.add_argument("--check-in", "-i", dest="check", action="store_const", const=1, help="Register a check in.")
args_group.add_argument("--check-out", "-o", dest="check", action="store_const", const=2, help="Register a check out.")
parser.add_argument("--reason", "-r", help="Specify the attendance reason ID for check out.")
parser.add_argument("--list-reasons", "-R", action="store_true", help="List the available reason ID with a brief description.")
args = parser.parse_args()

# Log in
common = client.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})

# Perform the requested action
if uid:
    models = client.ServerProxy('{}/xmlrpc/2/object'.format(url))

    if args.list_reasons:
        response = models.execute_kw(db, uid, password, 'hr.attendance.reason', 'search_read', [[]], {"fields": ["name"]})
        print("Available reason IDs:")
        print("ID\tName")
        print(("=" * max(len(str(response_item["id"])) for response_item in response)) + "\t" + ("=" * max(len(response_item["name"]) for response_item in response)))
        for response_item in response:
            print(str(response_item.get("id")) + "\t" + response_item.get("name"))
    else:
        # Get the current attendance_state
        response = models.execute_kw(db, uid, password, 'hr.employee', 'search_read', [[['user_id', '=', uid]]], {'fields': ['attendance_state']})
        employee_id = None
        for response_item in response:
            # Failsafe in case we get more than one result
            if employee_id is not None:
                print("Unexpected result when quering for current attendance state.")
                employee_id = None
                break

            employee_id = response_item.get("id")
            attendance_state = response_item.get("attendance_state")

        if employee_id:
            if args.check == 1:
                # Check in
                if attendance_state == "checked_in":
                    print("User already checked in, skipping...")
                elif attendance_state == "checked_out":
                    # Register the attendance
                    response = models.execute_kw(db, uid, password, 'hr.employee', 'attendance_manual', [employee_id, False])
                    action = response.get("action")
                    attendance = action.get("attendance")
                    print("Checked in as user \"" + username + "\" on " + attendance.get("check_in") + ".")
                else:
                    print("Unexpected attendance state: \"" + attendance_state + "\".")
            elif args.check == 2:
                # Check out
                if attendance_state == "checked_out":
                    print("User not checked in, skipping...")
                elif attendance_state == "checked_in":
                    # Register the attendance
                    response = models.execute_kw(db, uid, password, 'hr.employee', 'attendance_manual', [employee_id, False])
                    action = response.get("action")
                    attendance = action.get("attendance")
                    print("Checked out as user \"" + username + "\" on " + attendance.get("check_out") + ".")

                    if args.reason:
                        # Set a reason for the registered attendance
                        reason = int(args.reason)
                        response = models.execute_kw(db, uid, password, 'hr.attendance.reason', 'search_read', [[]], {"fields": ["id"]})
                        if not any(reasons.get("id") == reason for reasons in response):
                            print("Unknown reason ID:" + args.reason)
                        else:
                            # [6, False, [IDs]] deletes the current IDs and inserts the provided one(s) in a single operation
                            response = models.execute_kw(db, uid, password, 'hr.attendance', 'write', [[attendance.get("id")], {'attendance_reason_ids': [[6, False, [reason]]]}])
                            if response:
                                print("Attendance reason set.")
                            else:
                                print("Couldn't set attendance reason.")
                else:
                    print("Unexpected attendance state: \"" + attendance_state + "\".")
        else:
            print("None or multiple employee ID(s) found for user \"" + username + "\".")
else:
    print("Login failed.")