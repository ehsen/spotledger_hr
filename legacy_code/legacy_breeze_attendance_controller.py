from dataclasses import fields
from warnings import filters
import frappe
from frappe.exceptions import DuplicateEntryError, LinkValidationError,ValidationError
from frappe.utils import cstr, formatdate, get_datetime, getdate, nowdate,get_weekday,time_diff_in_seconds,datetime,get_time,add_to_date,get_date_str
#from erpnext.hr.doctype.holiday_list.holiday_list import is_holiday
from erpnext.hr.doctype.employee.employee import get_holiday_list_for_employee,is_holiday
import calendar
import anvil.server
from typing import List

from copy import deepcopy
import json


from frappe.utils.data import add_days


#Start from remote DB ID validation

def get_current_datetime(date_str:str,time_str:str,add_day=False) -> datetime.datetime:
        # Concate date & time strings and return datetime object
        if not add_day:
            return get_datetime(date_str + ' ' + str(time_str))
        elif add_day:
            dt = get_datetime(date_str + ' ' + str(time_str))
            return add_to_date(dt,day=1,as_datetime=True)
        
            

def calculate_total_hours(str_check_out:str,str_check_in:str,break_duration:int,dt_break_ends,is_friday):
        #TODO: Recheck this function 
        #TODO: As per discussion with Shabbir Sb, Calculate total hrs ignoring break time.
        #basically the factory consider net factory duration of 8.5 hrs. they dont get into detail 
        # 
        # calculate total hours in seconds
        
        #frappe.throw(check_out_before_break)
        total_seconds = time_diff_in_seconds(str_check_out,str_check_in) # break duration causing error
        #frappe.throw(str(settings_profile.friday_break_end))
        """
        if is_friday == 1:
            
            diff = get_datetime(str_check_out) - dt_break_ends.get('friday')
            
        elif is_friday == 0:
            diff = get_datetime(str_check_out) - dt_break_ends.get('regular')
        
        #frappe.throw(str(diff.total_seconds()))
        total_seconds = None
        if diff.total_seconds() <= 0:
            total_seconds = time_diff_in_seconds(str_check_out,str_check_in)
        elif diff.total_seconds() > 0:
            total_seconds = time_diff_in_seconds(str_check_out,str_check_in)-break_duration

        """

        return total_seconds

def get_break_duration(dt_checkout_after_grace:datetime.datetime,dt_break_ends_dict:dict,is_friday:int,break_duration:int,
                       dt_checkin_after_grace:datetime.datetime) -> int:
    
    if is_friday == 1:
        if (dt_checkout_after_grace <= dt_break_ends_dict.get('friday_start')) or dt_checkin_after_grace >= dt_break_ends_dict.get('friday_start'):
             return 0
        elif dt_checkout_after_grace > dt_break_ends_dict.get('friday'):
            return break_duration

    elif is_friday == 0:
        if (dt_checkout_after_grace <= dt_break_ends_dict.get('regular_start')) or dt_checkin_after_grace >= dt_break_ends_dict.get('regular_start'):
            return 0
        elif dt_checkout_after_grace > dt_break_ends_dict.get('regular'):
            return break_duration
        

        
    
    
     
     
        
        
        
        
    
    

def get_time_after_grace(str_check_in,grace_time_to_add,factory_time,attendance_date,settings_profile=None) -> datetime.datetime:
    #TODO: Warning this function will malfunction if Timezone not correctly set in Frappe and Underlying OS/locale
    dt_check_in = get_datetime(str_check_in)
    #frappe.throw(f"{factory_time}")
    dt_factory_time = get_current_datetime(attendance_date,factory_time)
    #dt_factory_time = get_current_datetime("2022-07-27","07:30")
    
    
    #max_check_in_time = add_to_date(dt_factory_time,minutes=30,as_datetime=True)
    max_check_in_time = add_to_date(dt_factory_time,minutes=settings_profile.maximum_grace_minutes,as_datetime=True)
    
    threshhold_check_in = add_to_date(dt_factory_time,minutes=grace_time_to_add,as_datetime=True)
    
    #frappe.throw(str({'dt_check_in':dt_check_in,'dt_factory_time':dt_factory_time,'max_check_in':max_check_in_time,'threshold':threshhold_check_in,'atten_date':attendance_date}))
    if dt_check_in <= threshhold_check_in: # upto grace period return check_in_time
        return dt_factory_time
        
    elif (dt_check_in > threshhold_check_in) and (dt_check_in <= max_check_in_time):
        return max_check_in_time
    
    elif dt_check_in > max_check_in_time:
    
    
        return dt_check_in

def get_time_after_grace_out(str_check_in,grace_time_to_add,factory_time,attendance_date,dt_break_ends=None,is_friday=None,settings_profile=None) -> datetime.datetime:
    #TODO: Warning this function will malfunction if Timezone not correctly set in Frappe and Underlying OS/locale
    dt_check_in = get_datetime(str_check_in)
    print(f"Factory time is {factory_time}")
    dt_factory_time = get_current_datetime(attendance_date,factory_time)
    friday_break_ends = dt_break_ends.get("friday")
    friday_break_start = dt_break_ends.get("friday_start")
    
    #max_check_in_time = add_to_date(dt_factory_time,minutes=30,as_datetime=True)
    max_check_in_time = add_to_date(dt_factory_time,minutes=settings_profile.maximum_grace_minutes,as_datetime=True)
    threshhold_check_in = add_to_date(dt_factory_time,minutes=grace_time_to_add,as_datetime=True)

    # In case of friday, If employee check out during prayer break. Time should be adjusted back to factory closing
    

    #frappe.throw(str(dt_break_ends))
    if is_friday == 1:
        if dt_check_in <= friday_break_start:
            #frappe.throw(f"{str(dt_check_in)}, friday = {str(friday_break_start)}")
            return dt_check_in
        elif dt_check_in <= friday_break_ends:
            return dt_factory_time
    
    if (dt_check_in <= threshhold_check_in) and (dt_check_in >= dt_factory_time): # upto grace period return check_in_time
        return dt_factory_time
        
    elif (dt_check_in > threshhold_check_in) and (dt_check_in <= max_check_in_time):
        return max_check_in_time
    
    elif dt_check_in > max_check_in_time:
        return dt_check_in
    
    elif dt_check_in < dt_factory_time:
        return dt_check_in

def handle_multi_day_time():
    pass
def calculate_reg_hours(check_out,check_in,required_factory_duration,break_duration,dt_break_ends,is_friday=0,adjusted_break_duration=0) -> int:
    total_hrs_worked = calculate_total_hours(check_out,check_in,break_duration,dt_break_ends,is_friday)
    #frappe.throw(f"checkout={str(check_out)}, check_in= {str(check_in)}, requiref_factory = {str(required_factory_duration)}, break={break_duration}")
    if adjusted_break_duration == None:
        adjusted_break_duration  = 0
    adjusted_total_hours = total_hrs_worked-adjusted_break_duration
    
    #Temporary fix for 
    net_factory_duration = required_factory_duration - break_duration
    if is_friday == 0:
        net_factory_duration = required_factory_duration - break_duration
    elif is_friday == 1:
        net_factory_duration = required_factory_duration

    
    if adjusted_total_hours > net_factory_duration:
        return net_factory_duration
    
    elif adjusted_total_hours <= net_factory_duration:
        
        return adjusted_total_hours

def calculate_overtime(check_out,check_in,required_factory_duration,break_duration,is_gazz,dt_break_ends,is_friday=0,ignore_break_factor=1,
                       forced_hours=0) -> int:
    
    if forced_hours == 1:
        break_duration = 0
    # For some employees break should nt be deducted while calculating overtime ignore break factor handle that.
    
    # Total hours deduct break even on friday. Howewver its been handled for Friday
    total_hrs_worked = calculate_total_hours(check_out,check_in,break_duration,dt_break_ends,is_friday)
    if is_friday == 0:
        #net_factory_duration = required_factory_duration - break_duration # temporarily commented out break
        
        net_factory_duration = required_factory_duration
    elif is_friday == 1:
        net_factory_duration = required_factory_duration
        

    if (is_gazz == 0) and (is_friday==0):
        if total_hrs_worked > net_factory_duration:
            return (total_hrs_worked - net_factory_duration)
    
    if (is_gazz == 0) and (is_friday==1):
        if total_hrs_worked > net_factory_duration:
            
            overtime = total_hrs_worked - net_factory_duration-(break_duration * ignore_break_factor)
            if overtime < 0:
                return 0
            else:
                return overtime


        elif (total_hrs_worked == net_factory_duration) or (total_hrs_worked < net_factory_duration):
            return 0
    
    if is_gazz == 1:
        return total_hrs_worked # All hours worked will be treated as overtime (Gazzetted Overtime)


def calculate_deficiency(total_hours_worked:int,required_factory_duration:int,break_duration:int,is_gazz:int,is_friday=0,adjusted_break_duration=0,
                         settings_profile=None) -> int:
    
    if adjusted_break_duration == None:
        adjusted_break_duration = 0
    if is_friday==0:
        net_factory_duration = required_factory_duration - break_duration
    elif is_friday == 1:
        if settings_profile.force_hours_to_work == 1:
            net_factory_duration = required_factory_duration
            
        else:
            
            net_factory_duration = required_factory_duration
    if is_gazz == 1:
        return 0
    elif is_gazz == 0:
        if total_hours_worked < net_factory_duration:
            deffi = net_factory_duration-total_hours_worked+adjusted_break_duration
            #frappe.throw(deffi)
            return deffi
        elif total_hours_worked >= net_factory_duration:
            return 0
    
def get_days_in_month(date):
    cur_date = getdate(date)
    days_in_month = calendar.monthrange(cur_date.year,cur_date.month)[1]
    return days_in_month


import sqlite3

def fetch_gate_entry_data(date_time:str, employees_data=None, db_path=None):
    today_date = datetime.datetime.now().strftime('%d-%m-%Y')
    
    # Use provided db_path or default
    #db_file = db_path if db_path else 'mydatabase.sqlite'
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # This enables dictionary-like access to rows
        cursor = conn.cursor()
        
        query = """
        select * from Attendance 
        WHERE DATETIME(SUBSTR(date, 7) || '-' || SUBSTR(date, 4, 2) || '-' || SUBSTR(date, 1, 2) || ' ' || check_in) > DATETIME(?)
        and date not like ?
        """
        
        cursor.execute(query, (date_time, f'%{today_date}%'))
        result = cursor.fetchall()
        
        # Convert rows to list of dictionaries
        result_list = [dict(row) for row in result]
        
        return result_list
        
    except sqlite3.Error as e:
        frappe.log_error(f"SQLite error: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()
"""
@frappe.whitelist()
def fetch_gate_entry_data(date_time:str):
    try:
        
        anvil.server.connect("server_CBFLSARELC6SMDH23BLHBKDQ-3XA5RRRYYD64QDS3")
        
        data=anvil.server.call('fetch_gate_entry_data',date_time)
        anvil.server.disconnect()
        return data
        
    
    except anvil.server.UplinkDisconnectedError:
        frappe.throw("Gate Entry System Is Not Connected To ERP. Please Connect It First Then Try Again")
    
    except Exception:
        #frappe.throw("ERP Failed to Communicate With Gate Entry System. Please Connect It First Then Try Again")
        raise
"""
    
def validate_employees(employee_list:list) -> list:
    not_validated = []
    for item in employee_list:
        employee = frappe.db.get_value("Employee",item.get("employee_code"))
        if employee:
            pass
        elif not employee:
            # try to fetch employee by breezecode
            
            not_validated.append(item.get("employee_code"))

    return not_validated

def get_friday_time_diff(employee):
    settings_profile_str = frappe.get_doc("Employee",employee).settings_profile
    if settings_profile_str is None:
        return 5.5
    settings_profile = frappe.get_doc("Breeze Payroll Settings",settings_profile_str)
    friday_time_diff = time_diff_in_seconds(settings_profile.friday_end_time,settings_profile.friday_start_time) or 0
    return friday_time_diff/3600


def get_date_pk(date_str):
    
    if isinstance(date_str,datetime.date):
        return date_str
    elif not isinstance(date_str,datetime.date):

        return datetime.datetime.strptime(date_str,"%d-%m-%Y").date()
    



def is_check_out_next_day(check_in_str,check_out_str):
    time_diff = get_time(check_out_str) - get_time(check_in_str)
    return time_diff

def convert_to_datetime(check_in_str,date_str):
    return get_datetime(f"{str(get_date_pk(date_str)) + ' ' + check_in_str}")

def validate_gate_entry_employee(employee_code):
    """
    This function try to check employee against the employee code in erpnext. 
    furthermore, it will try to fetch employee by breezecode.
    """
    try:
        doc = frappe.get_doc("Employee",employee_code)
        return doc.name
    except ValidationError:
        employee = frappe.db.sql(f"select name from tabEmployee  where breeze_code = '{employee_code}'",as_dict=1)
        print(employee)
        if len(employee) > 0:
            return employee[0].name
    
    return None


def create_gate_entry_doc(atten_dict):
    
    get_employee = validate_gate_entry_employee(atten_dict.employee_code)
    
    if get_employee is not None:    
        doc = frappe.get_doc({
            'doctype':"Gate Entry",
            'docstatus':0,
            #'employee':atten_dict.employee_code,
            'employee':get_employee,
            'attendance_date': atten_dict.date,
            'check_in':atten_dict.check_in,
            'check_out': atten_dict.check_out,
            'remote_db_id':atten_dict.id
        })
        doc.insert()
    
    else:
        print(f"Employee not found {atten_dict.employee_code}")
        frappe.log("Employee not found")


def validate_employees(attendance_data):
    employee_validation = validate_employees(attendance_data)
    if len(employee_validation) > 0:
        frappe.throw(str(employee_validation))






def add_day_in_checkout(check_in:datetime.datetime,check_out:datetime.datetime,date_str,check_out_str) -> datetime.datetime:
    if check_out is None: # Checkout could be None
        return None
    if check_out < check_in:
        date_after_addition = add_days(get_date_pk(date_str),1)
        # reconstruct check_out object
        check_out_obj = convert_to_datetime(check_out_str,date_after_addition)
        return check_out_obj
    else: # simply return the origincal check out 
        return check_out

def validate_check_in(attendance_dict):
    atten = frappe._dict(attendance_dict)
    if atten.check_in is None:
        return None
    elif atten.check_in is not None:
        
        return convert_to_datetime(atten.check_in,atten.date)

def validate_check_out(attendance_dict):
    atten = frappe._dict(attendance_dict)
    if atten.check_out is None:
        return None

    elif atten.check_out is not None:
        dt_check_out = convert_to_datetime(atten.check_out,atten.date)
        dt_check_in = validate_check_in(attendance_dict)
        if isinstance(dt_check_in,datetime.datetime) & isinstance(dt_check_out,datetime.datetime):
            dt_check_out_after_addition = add_day_in_checkout(dt_check_in,dt_check_out,atten.date,atten.check_out) 
            return dt_check_out_after_addition
def is_remote_db_exists(remote_db_id:int) -> bool:
    val = frappe.db.get_value(doctype="Gate Entry",filters={'remote_db_id':remote_db_id}) 
    if val is not None:
        return True
    elif val is None:
        return False


        
@frappe.whitelist()
def sync_attendance(gate_entry_logs=True,attendance_db_path=None):
    try:
        #frappe.log_error(message="Syncing Attendance",title="Syncing Attendance")
        db_path = frappe.get_site_path()+attendance_db_path
        gate_entry_producer = frappe.get_doc("Gate Entry Producer","Breeze Frost Industries (Pvt) Limited")
        last_update = gate_entry_producer.last_update
        if not last_update:
            raise Exception("Last Update Time Not Found In Gate Entry Producer")
        
        current_datetime = datetime.datetime.now()
        #last_update = "2022-08-31 23:59:00"
        atten_data_obj = fetch_gate_entry_data(last_update,db_path=db_path)
        #frappe.log_error(message=f"Attendance Data {atten_data_obj}",title="Attendance Data")
        #validate_employees()
        validation_failed = []
        sync_conflicts = []
        # check the last db
        # Generate Gate Entry Doc from attendance data
        #json_obj = json.loads(attendance_data)
        #atten_data_obj = json_obj[0]
        #last_id = json_obj[1]
        
        
        if gate_entry_logs:
            
            total_records = len(atten_data_obj)
            for index,item in enumerate(atten_data_obj):
                frappe.publish_progress(
                    percent=((index + 1) / total_records * 100),
                    title="Importing Attendance Records",
                    description=f"Processing record {index + 1} of {total_records}"
                )
                #frappe.throw(item)
                atten_dict = deepcopy(frappe._dict(item))
                atten_dict.check_in = validate_check_in(item)
                atten_dict.check_out = validate_check_out(item)
                atten_dict.date = get_date_pk(item.get("date"))
                # Insert Doc
                
                if not is_remote_db_exists(atten_dict.id):
                    print("creating log...")
                    create_gate_entry_doc(atten_dict)
                elif is_remote_db_exists(atten_dict.id):
                    print(f"remote db exists {atten_dict.id}")
                    pass # Skip the entry
                
                    
            
                
            
            gate_entry_producer.last_update = current_datetime
            gate_entry_producer.save()
            frappe.db.commit()
            
        elif not gate_entry_logs:
            pass
        
        return True
    except Exception as e:
        frappe.log_error(message=f"{e}",title="Sync Attendance Error")
        return False

def get_employees_new(date):
    #TODO: Ideally these operations should be performed in redis. Explore
   

    marked_employees = frappe.db.sql("""
    SELECT tabEmployee.name,is_exempt_attendance from tabEmployee left join
`tabBreeze Payroll Settings` on tabEmployee.settings_profile = `tabBreeze Payroll Settings`.name 
where is_exempt_attendance=0 and status="Active"  and tabEmployee.name in (select employee from tabAttendance where
attendance_date=%(attendance_date)s and docstatus=1)  
    """,values={'attendance_date':getdate(date)},as_dict=1)

    unmarked_employees = frappe.db.sql("""
    SELECT tabEmployee.name as employee,check_in,check_out from tabEmployee left join
`tabBreeze Payroll Settings` on tabEmployee.settings_profile = `tabBreeze Payroll Settings`.name 
left join `tabGate Entry` on 
tabEmployee.name = `tabGate Entry`.employee
where is_exempt_attendance=0 and status="Active"  and tabEmployee.name not in (select employee from tabAttendance where
attendance_date=%(attendance_date)s and docstatus=1) and remote_db_id is null 
    """,values={'attendance_date':getdate(date)},as_dict=1)

@frappe.whitelist()
def get_employees_with_attendance():
    sql = """
        select 

tabEmployee.name,
tabEmployee.employee_name
 
from tabEmployee

left join `tabBreeze Payroll Settings` on 
`tabBreeze Payroll Settings`.name = tabEmployee.settings_profile
where is_exempt_attendance = 0
    """
    
    result = frappe.db.sql(sql,as_dict=1)
    return result








    return {"marked":marked_employees,"unmarked":unmarked_employees}
   



        
    

@frappe.whitelist()
def test_button():
    frappe.msgprint("Hello")


@frappe.whitelist()
def fetch_last_id():
    # fetch the last synced ID
    try:
        last_id = frappe.db.sql("select remote_db_id from `tabGate Entry` order by remote_db_id desc limit 1;",as_list=1)[0]
    
        if len(last_id )> 0:
            #frappe.msgprint(last_id)
        
            return last_id[0]
        else:
            return 0
    except IndexError as e:
        frappe.log_error(e)
        return 0

def validate_unmarked(atten_dict):
        
        
        for idx,item in enumerate(atten_dict):
            item = frappe._dict(item)
            #type_list.append(str(type(item.check_out_time)))
            if item.check_out_time is None:
                
                frappe.throw("Please fix errors in Unmarked Employees. Missing Time")
                
                
            if  item.check_in_time is None:
                
                frappe.throw((f"Please fix errors in Unmarked Employees. Missing Time"))

def validate_absent(atten_dict):

        
        
        
        for idx,item in enumerate(atten_dict):
            item = frappe._dict(item)
            #type_list.append(str(type(item.check_out_time)))
            
            if item.status == "Present":
                if (item.check_in_time or item.check_out_time) is None:
                    frappe.throw("Missing time in Absent Employees List")
            elif item.status == "Absent":
                pass
@frappe.whitelist()
def mark_bulk_attendance(atten_date,unmarked_list_json,absent_list_json,json_data=True):
        
        if json_data:
            unmarked_list = json.loads(unmarked_list_json)
            absent_list = json.loads(absent_list_json)
        else: 
            unmarked_list = unmarked_list_json
            absent_list = absent_list_json
            pass
        
        
        validate_unmarked(unmarked_list)
        validate_absent(absent_list)

        
            # Generate Attendance for Unmarked
        for item in unmarked_list:
            item = frappe._dict(item)
            #print('*****************************')
            #print(f"Preparing Attendance Doc for {item}")	
            prepare_attendance_doc(atten_date,item)
            print(f"Generating attendance for {item}")
            #print("Attendance Doc Created")
            # Generate attendance for Absent

        for item in absent_list:
            #TODO: Skip generating absent docs for sunday & gazzetted hoidays
            
            if get_datetime(atten_date).weekday() != 6:
                
                item = frappe._dict(item)
                print(f"Generating attendance for {item}")
                prepare_attendance_doc(atten_date,item)
        
        frappe.msgprint("Attendanced Succefully Marked")

@frappe.whitelist()
def get_employees_data(date, department = None, branch = None, company = None):
    
    
    attendance_not_marked = []
    unmarked_employees_list = []
    attendance_marked = []
    gate_entry_docs = []
    attendance_docs = []
        #frappe.throw(str(date.date))
            
        

    filters = {"status": "Active", "date_of_joining": ["<=", date]}

    for field, value in {'department': department,
        'branch': branch, 'company': company}.items():
        if value:
            filters[field] = value

    employee_list = frappe.get_list("Employee", fields=["employee", "employee_name"], filters=filters, order_by="employee_name")
    marked_employee = {}
        
    for emp in frappe.get_list("Attendance", fields=["employee", "status","check_in_time","check_out_time","company","employee_name"],
                                filters={"attendance_date": date}):
        marked_employee[emp['employee']] = emp['status']
            #marked_employee[emp['check_in_time']] = emp['check_in_time']
            #marked_employee[emp['check_out_time']] = emp['check_out_time']
        attendance_docs.append(emp)
            
    for employee in employee_list:
            
        employee['status'] = marked_employee.get(employee['employee'])
        #employee['check_in'] = marked_employee.get(employee['check_in_time'])
        if employee['employee'] not in marked_employee:
            attendance_not_marked.append(employee)
            unmarked_employees_list.append(employee['employee'])
        else:
            attendance_marked.append(employee)
        
    if len(attendance_not_marked) > 0:
        #gate_entry_doc = frappe.get_list
        
        gate_entry_docs=frappe.db.get_list("Gate Entry",filters={'employee':['in',unmarked_employees_list],'attendance_date':['=',date]},
        fields=['employee','check_in','check_out','employee_name','remote_db_id'])
        
        
            
    atten_dict= {
        "marked": attendance_marked,
        "unmarked": attendance_not_marked,
        "gate_entry_docs":gate_entry_docs,
        "attendance_docs":attendance_docs,
        "absent_employees":gen_empty_gate_entry_docs(date)
            
        }
    
    return atten_dict

def is_exempt_from_negative_hours(employee):
        employee_doc = frappe.get_cached_doc("Employee",employee)
        if employee_doc.exempt_negative_hours == 1:
            return 0
        else:
            return 1

def gen_empty_gate_entry_docs(date):
    # Add empty gat entry docs for absent employees
    absent_employees = frappe.db.sql("""

        SELECT tabEmployee.name as employee,tabEmployee.employee_name, null as check_in,null as check_out from tabEmployee left join
        `tabBreeze Payroll Settings` on tabEmployee.settings_profile = `tabBreeze Payroll Settings`.name 
        where is_exempt_attendance=0 and status="Active"  and tabEmployee.name not in (select employee from tabAttendance where
        attendance_date=%(attendance_date)s and docstatus=1) and tabEmployee.name not in ( select employee from `tabGate Entry` where
        attendance_date=%(attendance_date)s)
    """,values={'attendance_date':date},as_dict=1)

    return absent_employees
            
def prepare_attendance_doc(atten_date,atten_obj):
        if atten_obj.status == "Present":
            doc = frappe.get_doc(
            {"doctype":"Attendance",
            "docstatus":1,
            "employee":atten_obj.employee,
            "attendance_date":atten_date,
            "status":atten_obj.status,
            "company":atten_obj.company,
            "check_in_time":atten_obj.check_in_time,
            "check_out_time":atten_obj.check_out_time})
        elif atten_obj.status == "Absent":
            doc = frappe.get_doc(
            {"doctype":"Attendance",
            "docstatus":1,
            "employee":atten_obj.employee,
            "attendance_date":atten_date,
            "status":atten_obj.status,
            "check_in_time":f"{atten_date + ' ' + '00:00:00'}",
            "check_out_time":f"{atten_date + ' ' + '00:00:00'}",

            "company":atten_obj.company})
        
        doc.insert()
    
def generate_dates(year: int, month: int):
    from datetime import datetime,timedelta
    dates = []

    # Get the first day of the month
    date = datetime(year, month, 1)

    # Continue until the next month
    while date.month == month:
        dates.append(date.date())
        date += timedelta(days=1)

    return dates

def update_atten_dict(date,unmarked_list,absent_employees,gate_entry_docs):
    
    updated_unmarked_list = []
    absent_updated_list = []
    for item in unmarked_list:
        
        gate_entry_filter = [d for d in gate_entry_docs if item['employee'] == d['employee']]
        if len(gate_entry_filter) > 0:
            gate_entry_doc = gate_entry_filter[0]
            
            item['attendance_date'] = date
            item['status'] = "Present"
            item['company'] = "Breeze Frost Industries (Pvt) Limited"
            item['check_in_time'] =  gate_entry_doc.check_in
            item['check_out_time'] = gate_entry_doc.check_out
            updated_unmarked_list.append(item)
        
    for item in absent_employees:
        item['attendance_date'] = date
        item['status'] = "Absent"
        item['company'] = "Breeze Frost Industries (Pvt) Limited"
        absent_updated_list.append(item)
    
    atten_dict = {
        'updated_unmarked_list':updated_unmarked_list,
        'updated_absent_list':absent_updated_list
    }
    return atten_dict
        
         
              

        
    
    

def mark_auto_attendance(year,month):
    errors = []
    days = generate_dates(year,month)
    for day in days:
        print(f"Generating Attendance for {str(day)}")
        atten_dict = get_employees_data(day)
        gate_entry_docs = frappe.get_list("Gate Entry",filters={'attendance_date':get_date_str(day)},fields=['*'])
        
        update_dict = update_atten_dict(day,atten_dict['unmarked'],atten_dict['absent_employees'],gate_entry_docs)
        #print(atten_dict['attendance_docs'])
        #print(atten_dict['absent_employees'])
        #print(update_dict)
        print("___________________________________________________________________________________________")
        
        try:
            mark_bulk_attendance(get_date_str(day),update_dict['updated_unmarked_list'],update_dict['updated_absent_list'],json_data=False)
            print("Attendance Generated")
        except ValidationError as e:
            errors.append(e)
            continue
        
    return len(errors)
        
        


def delete_attendance_docs(start_date, end_date):
    attendance_docs = frappe.get_all(
        'Attendance',
        filters={
            'docstatus': ['in', [0, 1]],
            'attendance_date': ['between', [start_date, end_date]]
        },
        fields=['name', 'docstatus']
    )

    for doc in attendance_docs:
        docname = doc.name
        docstatus = doc.docstatus

        try:
            if docstatus == 2:  # If doc status is "Cancelled"
                # Delete the document right away
                frappe.delete_doc('Attendance', docname, ignore_missing=True)
                print(f"Deleted cancelled document: {docname}")

            elif docstatus == 1:  # If doc status is "Submitted"
                # Cancel the document first
                attendance_doc = frappe.get_doc('Attendance', docname)
                attendance_doc.cancel()
                print(f"Cancelled submitted document: {docname}")

                # Delete the document
                frappe.delete_doc('Attendance', docname, ignore_missing=True)
                print(f"Deleted cancelled document: {docname}")

            else:
                # Handle any other doc status as per your requirement
                pass

        except frappe.LinkExistsError as e:
            # Handle the exception when document is linked to a salary slip
            # You can log the error or perform any necessary actions
            print(f"Error deleting document: {docname}. {e}")

    print("Process completed.")




def get_friday_absent_count(employee_id,start_date,end_date):
    sql_query = """
        SELECT
  attendance.employee AS employee,
  friday_dates.date AS date,
  IFNULL(attendance.status, 'None') AS status,
  WEEKDAY(friday_dates.date) + 1 as week_day,
  holiday.holiday_date as holiday_date
FROM
  (
    SELECT
      start_date + INTERVAL (n - 1) DAY AS date
    FROM
      (
        SELECT
          '{start_date}' AS start_date,
          '{end_date}' AS end_date,
          (DATEDIFF('{end_date}', '{start_date}') + 1) AS days
      ) date_range
    JOIN
      (
        SELECT (a.N + b.N * 10 + 1) AS n
        FROM
          (SELECT 0 AS N UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) a
          JOIN
          (SELECT 0 AS N UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9) b
      ) numbers
      ON n <= date_range.days
  ) friday_dates
LEFT JOIN
  `tabAttendance` attendance
ON
  friday_dates.date = attendance.attendance_date
AND
  attendance.employee = '{employee_id}'
LEFT JOIN
  `tabHoliday` holiday
ON
  friday_dates.date = holiday.holiday_date
WHERE
  WEEKDAY(friday_dates.date) + 1 = 5
ORDER BY
  friday_dates.date DESC;



    """.format(employee_id=employee_id,start_date=start_date,end_date=end_date)

    result = frappe.db.sql(sql_query, as_dict=True)
    absent_count = 0
    for item in result:
        if ((item['employee'] is None) and (item['holiday_date'] is None)):
            absent_count += 1
        
        elif ((item['employee'] is not None) and (item['status'] == 'Absent') and (item['holiday_date'] is None)):
            absent_count += 1
    
    return absent_count
    
    

    
    



        





        
        
        
        
    

    


    







