# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt


from calendar import monthrange
from itertools import groupby
from typing import Dict, List, Optional, Tuple

import frappe
from frappe import _
from frappe.query_builder.functions import Count, Extract, Sum
from frappe.utils import cint, cstr, getdate

Filters = frappe._dict

status_map = {
	"Present": "P",
	"Absent": "A",
	"Half Day": "HD",
	"Work From Home": "WFH",
	"On Leave": "L",
	"Holiday": "H",
	"Weekly Off": "WO",
}

day_abbr = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def execute(filters: Optional[Filters] = None) -> Tuple:
	filters = frappe._dict(filters or {})

	if not (filters.month and filters.year):
		frappe.throw(_("Please select month and year."))

	attendance_map = get_attendance_map(filters)
	if not attendance_map:
		frappe.msgprint(_("No attendance records found."), alert=True, indicator="orange")
		return [], [], None, None

	columns = get_columns(filters)
	data = get_data(filters, attendance_map)

	if not data:
		frappe.msgprint(
			_("No attendance records found for this criteria."), alert=True, indicator="orange"
		)
		return columns, [], None, None

	message = get_message() if not filters.summarized_view else ""
	chart = get_chart_data(attendance_map, filters)

	return columns, data, message, chart


def get_message() -> str:
	message = ""
	colors = ["green", "red", "orange", "green", "#318AD8", "", ""]

	count = 0
	for status, abbr in status_map.items():
		message += f"""
			<span style='border-left: 2px solid {colors[count]}; padding-right: 12px; padding-left: 5px; margin-right: 3px;'>
				{status} - {abbr}
			</span>
		"""
		count += 1

	return message


def get_columns(filters: Filters) -> List[Dict]:
	columns = []

	if filters.group_by:
		columns.append(
			{
				"label": _(filters.group_by),
				"fieldname": frappe.scrub(filters.group_by),
				"fieldtype": "Link",
				"options": "Branch",
				"width": 120,
			}
		)

	columns.extend(
		[
			{
				"label": _("Employee"),
				"fieldname": "employee",
				"fieldtype": "Link",
				"options": "Employee",
				"width": 135,
			},
			{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 120},
		]
	)

	if filters.summarized_view:
		columns.extend(
			[
				{
					"label": _("Total Present"),
					"fieldname": "total_present",
					"fieldtype": "Float",
					"width": 110,
				},
				{"label": _("Total Leaves"), "fieldname": "total_leaves", "fieldtype": "Float", "width": 110},
				{"label": _("Total Absent"), "fieldname": "total_absent", "fieldtype": "Float", "width": 110},
				{
					"label": _("Total Holidays"),
					"fieldname": "total_holidays",
					"fieldtype": "Float",
					"width": 120,
				},
				{
					"label": _("Unmarked Days"),
					"fieldname": "unmarked_days",
					"fieldtype": "Float",
					"width": 130,
				},
			]
		)
		columns.extend(get_columns_for_leave_types())
		columns.extend(
			[
				{
					"label": _("Total Late Entries"),
					"fieldname": "total_late_entries",
					"fieldtype": "Float",
					"width": 140,
				},
				{
					"label": _("Total Early Exits"),
					"fieldname": "total_early_exits",
					"fieldtype": "Float",
					"width": 140,
				},
			]
		)
	else:
		columns.append({"label": _("Shift"), "fieldname": "shift", "fieldtype": "Data", "width": 120})
		columns.extend(get_columns_for_days(filters))

	return columns


def get_columns_for_leave_types() -> List[Dict]:
	leave_types = frappe.db.get_all("Leave Type", pluck="name")
	types = []
	for entry in leave_types:
		types.append(
			{"label": entry, "fieldname": frappe.scrub(entry), "fieldtype": "Float", "width": 120}
		)

	return types


def get_columns_for_days(filters: Filters) -> List[Dict]:
	total_days = get_total_days_in_month(filters)
	days = []

	for day in range(1, total_days + 1):
		# forms the dates from selected year and month from filters
		date = "{}-{}-{}".format(cstr(filters.year), cstr(filters.month), cstr(day))
		# gets abbr from weekday number
		weekday = day_abbr[getdate(date).weekday()]
		# sets days as 1 Mon, 2 Tue, 3 Wed
		label = "{} {}".format(cstr(day), weekday)
		days.append({"label": label, "fieldtype": "Data", "fieldname": day, "width": 65})

	return days


def get_total_days_in_month(filters: Filters) -> int:
	return monthrange(cint(filters.year), cint(filters.month))[1]


def get_data(filters: Filters, attendance_map: Dict) -> List[Dict]:
	employee_details, group_by_param_values = get_employee_related_details(filters)
	holiday_map = get_holiday_map(filters)
	data = []

	if filters.group_by:
		group_by_column = frappe.scrub(filters.group_by)

		for value in group_by_param_values:
			if not value:
				continue

			records = get_rows(employee_details[value], filters, holiday_map, attendance_map)

			if records:
				data.append({group_by_column: frappe.bold(value)})
				data.extend(records)
	else:
		data = get_rows(employee_details, filters, holiday_map, attendance_map)

	return data


def get_attendance_map(filters: Filters) -> Dict:
	"""Returns a dictionary of employee wise attendance map as per shifts for all the days of the month like
	{
			'employee1': {
					'Morning Shift': {1: 'Present', 2: 'Absent', ...}
					'Evening Shift': {1: 'Absent', 2: 'Present', ...}
			},
			'employee2': {
					'Afternoon Shift': {1: 'Present', 2: 'Absent', ...}
					'Night Shift': {1: 'Absent', 2: 'Absent', ...}
			}
	}
	"""
	Attendance = frappe.qb.DocType("Attendance")
	query = (
		frappe.qb.from_(Attendance)
		.select(
			Attendance.employee,
			Extract("day", Attendance.attendance_date).as_("day_of_month"),
			Attendance.status,
			Attendance.shift,
		)
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.company == filters.company)
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	)
	if filters.employee:
		query = query.where(Attendance.employee == filters.employee)
	query = query.orderby(Attendance.employee, Attendance.attendance_date)

	attendance_list = query.run(as_dict=1)
	attendance_map = {}

	for d in attendance_list:
		attendance_map.setdefault(d.employee, frappe._dict()).setdefault(d.shift, frappe._dict())
		attendance_map[d.employee][d.shift][d.day_of_month] = d.status

	return attendance_map


def get_employee_related_details(filters: Filters) -> Tuple[Dict, List]:
	"""Returns
	1. nested dict for employee details
	2. list of values for the group by filter
	"""
	Employee = frappe.qb.DocType("Employee")
	query = (
		frappe.qb.from_(Employee)
		.select(
			Employee.name,
			Employee.employee_name,
			Employee.designation,
			Employee.grade,
			Employee.department,
			Employee.branch,
			Employee.company,
			Employee.holiday_list,
		)
		.where(Employee.company == filters.company)
	)

	if filters.employee:
		query = query.where(Employee.name == filters.employee)

	group_by = filters.group_by
	if group_by:
		group_by = group_by.lower()
		query = query.orderby(group_by)

	employee_details = query.run(as_dict=True)

	group_by_param_values = []
	emp_map = {}

	if group_by:
		for parameter, employees in groupby(employee_details, key=lambda d: d[group_by]):
			group_by_param_values.append(parameter)
			emp_map.setdefault(parameter, frappe._dict())

			for emp in employees:
				emp_map[parameter][emp.name] = emp
	else:
		for emp in employee_details:
			emp_map[emp.name] = emp

	return emp_map, group_by_param_values


def get_holiday_map(filters: Filters) -> Dict[str, List[Dict]]:
	"""
	Returns a dict of holidays falling in the filter month and year
	with list name as key and list of holidays as values like
	{
			'Holiday List 1': [
					{'day_of_month': '0' , 'weekly_off': 1},
					{'day_of_month': '1', 'weekly_off': 0}
			],
			'Holiday List 2': [
					{'day_of_month': '0' , 'weekly_off': 1},
					{'day_of_month': '1', 'weekly_off': 0}
			]
	}
	"""
	# add default holiday list too
	holiday_lists = frappe.db.get_all("Holiday List", pluck="name")
	default_holiday_list = frappe.get_cached_value("Company", filters.company, "default_holiday_list")
	holiday_lists.append(default_holiday_list)

	holiday_map = frappe._dict()
	Holiday = frappe.qb.DocType("Holiday")

	for d in holiday_lists:
		if not d:
			continue

		holidays = (
			frappe.qb.from_(Holiday)
			.select(Extract("day", Holiday.holiday_date).as_("day_of_month"), Holiday.weekly_off)
			.where(
				(Holiday.parent == d)
				& (Extract("month", Holiday.holiday_date) == filters.month)
				& (Extract("year", Holiday.holiday_date) == filters.year)
			)
		).run(as_dict=True)

		holiday_map.setdefault(d, holidays)

	return holiday_map


def get_rows(
	employee_details: Dict, filters: Filters, holiday_map: Dict, attendance_map: Dict
) -> List[Dict]:
	records = []
	default_holiday_list = frappe.get_cached_value("Company", filters.company, "default_holiday_list")

	for employee, details in employee_details.items():
		emp_holiday_list = details.holiday_list or default_holiday_list
		holidays = holiday_map.get(emp_holiday_list)

		employee_attendance = attendance_map.get(employee)
		if not employee_attendance:
			continue
		attendance_for_employee = get_attendance_status_for_detailed_view(
			employee, filters, employee_attendance, holidays
		)
		# set employee details in the first row
		attendance_for_employee[0].update(
			{"employee": employee, "employee_name": details.employee_name}
		)
		# get checkin data
		intime_data,outtime_data,total_working_data = get_attendance_details(attendance_for_employee,filters)
		# append data
		attendance_for_employee.append(
			{"shift": "In Time"}
		)
		attendance_for_employee[1].update(intime_data)
		# append data
		attendance_for_employee.append(
			{"shift": "Out Time"}
		)
		attendance_for_employee[2].update(outtime_data)
		# append data
		attendance_for_employee.append(
			{"shift": "Total Worked Hours"}
		)
		attendance_for_employee[3].update(total_working_data)
		# print(attendance_for_employee)
		records.extend(attendance_for_employee)

	return records

# [{'shift': 'General', 1: 'H', 2: '', 3: 'P', 4: 'A', 5: '', 6: '', 7: 'P', 8: 'P', 9: 'A', 10: 'P', 11: 'P', 12: '', 13: '', 14: 'P', 15: 'P', 16: 'A', 17: 'P', 18: '', 19: '', 20: '', 21: '', 22: '', 23: '', 24: '', 25: '', 26: '', 27: '', 28: '', 29: '', 30: '', 31: '', 'employee': 'NV119', 'employee_name': 'Prakash Ravindranath Rane'}]
def get_attendance_details(data,filters):
	# print("data in get_attendance_details")
	intime_data = {}
	outtime_data = {}
	total_working_data = {}
	for key,value in data[0].items():
		if isinstance(key,int):
			# if data[0].get('row') in ['P','H']:
			attendance_date = str(key)+"-"+filters.get('month')+"-"+filters.get("year")
			# print('''Attendance Date {0}'''.format(attendance_date))
			attendance_details = frappe.db.get_all("Attendance",filters={"employee":data[0].get("employee"),"shift":data[0].get("shift"),"attendance_date":attendance_date},fields=["in_time","out_time","working_hours"])
			if attendance_details:
				intime_data.setdefault(key,attendance_details[0]["in_time"])
				outtime_data.setdefault(key,attendance_details[0]["out_time"])
				total_working_data.setdefault(key, attendance_details[0]["working_hours"])

	return intime_data,outtime_data,total_working_data


def set_defaults_for_summarized_view(filters, row):
	for entry in get_columns(filters):
		if entry.get("fieldtype") == "Float":
			row[entry.get("fieldname")] = 0.0


def get_attendance_status_for_summarized_view(
	employee: str, filters: Filters, holidays: List
) -> Dict:
	"""Returns dict of attendance status for employee like
	{'total_present': 1.5, 'total_leaves': 0.5, 'total_absent': 13.5, 'total_holidays': 8, 'unmarked_days': 5}
	"""
	summary, attendance_days = get_attendance_summary_and_days(employee, filters)
	if not any(summary.values()):
		return {}

	total_days = get_total_days_in_month(filters)
	total_holidays = total_unmarked_days = 0

	for day in range(1, total_days + 1):
		if day in attendance_days:
			continue

		status = get_holiday_status(day, holidays)
		if status in ["Weekly Off", "Holiday"]:
			total_holidays += 1
		elif not status:
			total_unmarked_days += 1

	return {
		"total_present": summary.total_present + summary.total_half_days,
		"total_leaves": summary.total_leaves + summary.total_half_days,
		"total_absent": summary.total_absent,
		"total_holidays": total_holidays,
		"unmarked_days": total_unmarked_days,
	}


def get_attendance_summary_and_days(employee: str, filters: Filters) -> Tuple[Dict, List]:
	Attendance = frappe.qb.DocType("Attendance")

	present_case = (
		frappe.qb.terms.Case()
		.when(((Attendance.status == "Present") | (Attendance.status == "Work From Home")), 1)
		.else_(0)
	)
	sum_present = Sum(present_case).as_("total_present")

	absent_case = frappe.qb.terms.Case().when(Attendance.status == "Absent", 1).else_(0)
	sum_absent = Sum(absent_case).as_("total_absent")

	leave_case = frappe.qb.terms.Case().when(Attendance.status == "On Leave", 1).else_(0)
	sum_leave = Sum(leave_case).as_("total_leaves")

	half_day_case = frappe.qb.terms.Case().when(Attendance.status == "Half Day", 0.5).else_(0)
	sum_half_day = Sum(half_day_case).as_("total_half_days")

	summary = (
		frappe.qb.from_(Attendance)
		.select(
			sum_present,
			sum_absent,
			sum_leave,
			sum_half_day,
		)
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.employee == employee)
			& (Attendance.company == filters.company)
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	).run(as_dict=True)

	days = (
		frappe.qb.from_(Attendance)
		.select(Extract("day", Attendance.attendance_date).as_("day_of_month"))
		.distinct()
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.employee == employee)
			& (Attendance.company == filters.company)
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	).run(pluck=True)

	return summary[0], days


def get_attendance_status_for_detailed_view(
	employee: str, filters: Filters, employee_attendance: Dict, holidays: List
) -> List[Dict]:
	"""Returns list of shift-wise attendance status for employee
	[
			{'shift': 'Morning Shift', 1: 'A', 2: 'P', 3: 'A'....},
			{'shift': 'Evening Shift', 1: 'P', 2: 'A', 3: 'P'....}
	]
	"""
	total_days = get_total_days_in_month(filters)
	attendance_values = []

	for shift, status_dict in employee_attendance.items():
		row = {"shift": shift}

		for day in range(1, total_days + 1):
			status = status_dict.get(day)
			if status is None and holidays:
				status = get_holiday_status(day, holidays)

			abbr = status_map.get(status, "")
			row[day] = abbr

		attendance_values.append(row)

	return attendance_values


def get_holiday_status(day: int, holidays: List) -> str:
	status = None
	if holidays:
		for holiday in holidays:
			if day == holiday.get("day_of_month"):
				if holiday.get("weekly_off"):
					status = "Weekly Off"
				else:
					status = "Holiday"
				break
	return status


def get_leave_summary(employee: str, filters: Filters) -> Dict[str, float]:
	"""Returns a dict of leave type and corresponding leaves taken by employee like:
	{'leave_without_pay': 1.0, 'sick_leave': 2.0}
	"""
	Attendance = frappe.qb.DocType("Attendance")
	day_case = frappe.qb.terms.Case().when(Attendance.status == "Half Day", 0.5).else_(1)
	sum_leave_days = Sum(day_case).as_("leave_days")

	leave_details = (
		frappe.qb.from_(Attendance)
		.select(Attendance.leave_type, sum_leave_days)
		.where(
			(Attendance.employee == employee)
			& (Attendance.docstatus == 1)
			& (Attendance.company == filters.company)
			& ((Attendance.leave_type.isnotnull()) | (Attendance.leave_type != ""))
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
		.groupby(Attendance.leave_type)
	).run(as_dict=True)

	leaves = {}
	for d in leave_details:
		leave_type = frappe.scrub(d.leave_type)
		leaves[leave_type] = d.leave_days

	return leaves


def get_entry_exits_summary(employee: str, filters: Filters) -> Dict[str, float]:
	"""Returns total late entries and total early exits for employee like:
	{'total_late_entries': 5, 'total_early_exits': 2}
	"""
	Attendance = frappe.qb.DocType("Attendance")

	late_entry_case = frappe.qb.terms.Case().when(Attendance.late_entry == "1", "1")
	count_late_entries = Count(late_entry_case).as_("total_late_entries")

	early_exit_case = frappe.qb.terms.Case().when(Attendance.early_exit == "1", "1")
	count_early_exits = Count(early_exit_case).as_("total_early_exits")

	entry_exits = (
		frappe.qb.from_(Attendance)
		.select(count_late_entries, count_early_exits)
		.where(
			(Attendance.docstatus == 1)
			& (Attendance.employee == employee)
			& (Attendance.company == filters.company)
			& (Extract("month", Attendance.attendance_date) == filters.month)
			& (Extract("year", Attendance.attendance_date) == filters.year)
		)
	).run(as_dict=True)

	return entry_exits[0]


@frappe.whitelist()
def get_attendance_years() -> str:
	"""Returns all the years for which attendance records exist"""
	Attendance = frappe.qb.DocType("Attendance")
	year_list = (
		frappe.qb.from_(Attendance)
		.select(Extract("year", Attendance.attendance_date).as_("year"))
		.distinct()
	).run(as_dict=True)

	if year_list:
		year_list.sort(key=lambda d: d.year, reverse=True)
	else:
		year_list = [frappe._dict({"year": getdate().year})]

	return "\n".join(cstr(entry.year) for entry in year_list)


def get_chart_data(attendance_map: Dict, filters: Filters) -> Dict:
	days = get_columns_for_days(filters)
	labels = []
	absent = []
	present = []
	leave = []

	for day in days:
		labels.append(day["label"])
		total_absent_on_day = total_leaves_on_day = total_present_on_day = 0

		for employee, attendance_dict in attendance_map.items():
			for shift, attendance in attendance_dict.items():
				attendance_on_day = attendance.get(day["fieldname"])

				if attendance_on_day == "Absent":
					total_absent_on_day += 1
				elif attendance_on_day in ["Present", "Work From Home"]:
					total_present_on_day += 1
				elif attendance_on_day == "Half Day":
					total_present_on_day += 0.5
					total_leaves_on_day += 0.5
				elif attendance_on_day == "On Leave":
					total_leaves_on_day += 1

		absent.append(total_absent_on_day)
		present.append(total_present_on_day)
		leave.append(total_leaves_on_day)

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": "Absent", "values": absent},
				{"name": "Present", "values": present},
				{"name": "Leave", "values": leave},
			],
		},
		"type": "line",
		"colors": ["red", "green", "blue"],
	}
