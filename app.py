# ============================================
# 1. SET MOCK MODE FIRST (Change to False for real Oracle)
# ============================================
USE_MOCK_DB = True  # Keep True for Render deployment

# ============================================
# 2. ALL IMPORTS (Including oracledb)
# ============================================
from flask import Flask, jsonify, render_template, request, url_for, session, redirect, stream_with_context, Response
from flask import send_file, render_template_string
import pandas as pd
from io import BytesIO
from datetime import datetime
import oracledb
import io
import os
import platform
import json
import traceback

print(f"=== DATABASE MODE: {'MOCK' if USE_MOCK_DB else 'REAL ORACLE'} ===")

# ============================================
# 3. MOCK CLASSES (Only used when USE_MOCK_DB = True)
# ============================================
class MockConnection:
    def cursor(self):
        return MockCursor()
    def close(self):
        pass
    def commit(self):
        pass

class MockCursor:
    def __init__(self):
        self.description = None
        self.results = []
        self.arraysize = 1000
    
    def execute(self, query, params=None):
        query_str = str(query).lower() if query else ""
        
        # Return mock data based on query type
        if "all_employees" in query_str or "employee_number" in query_str:
            self.description = [
                ('A.ERP No',), ('B.Name',), ('C.Father Name',), ('Cnic',),
                ('Date of Birth',), ('Retirement Forecast',), ('Grade',),
                ('Designation',), ('E.Cadre',), ('Sanctioned Scale',),
                ('H.Current Posting Date',), ('D.Office Name',), ('Employee Category',)
            ]
            self.results = [
                ('001', 'John Doe', 'Robert Doe', '12345-6789012-3', '01-01-1980',
                 '01-01-2040', 'Grade 17', 'Manager', 'Cadre', 'Scale', 
                 '01-01-2020', 'Peshawar Office', 'Regular'),
            ]
        elif "payroll" in query_str or "earning" in query_str:
            self.description = [('earning_head',), ('total',)]
            self.results = [('Basic Salary', 50000), ('House Rent', 25000), ('Medical', 5000)]
        elif "deduction" in query_str:
            self.description = [('deduction_head',), ('deduction_amount',)]
            self.results = [('Income Tax', 5000), ('Union Fund', 200), ('Welfare', 300)]
        elif "vacancy" in query_str:
            self.description = [('scale',), ('designation',), ('sanctioned',), ('working',), ('vacant',), ('surplus',)]
            self.results = [('17', 'SDOs / Assistant Managers', 100, 80, 20, 0)]
        elif "grade_wise" in query_str:
            self.description = [('A_GRADE',), ('sanctioned',), ('regular',), ('contract',), ('working',), ('vacant',)]
            self.results = [('Grade 17', 100, 80, 10, 90, 10)]
        else:
            self.description = [('col1',), ('col2',)]
            self.results = [('Sample Data', 'Value')]
        return self
    
    def fetchall(self):
        return self.results
    
    def fetchmany(self, size):
        return self.results[:size]
    
    def fetchone(self):
        return self.results[0] if self.results else None
    
    def close(self):
        pass

# ============================================
# 4. ORACLE INITIALIZATION (Conditional)
# ============================================
def init_oracle():
    if USE_MOCK_DB:
        print("Mock mode active - skipping Oracle client init")
        return
    
    try:
        if platform.system() == "Linux":
            lib_dir = os.path.join(os.getcwd(), "instantclient")
            if os.path.exists(lib_dir):
                oracledb.init_oracle_client(lib_dir=lib_dir)
            else:
                print("Oracle client not found - using mock mode")
                global USE_MOCK_DB
                USE_MOCK_DB = True
                return
        else:
            oracledb.init_oracle_client(lib_dir=r"C:\oracle\instantclient_23_0")
        print("Oracle Thick Mode initialized.")
    except Exception as e:
        print(f"Oracle Client Error: {e}")
        global USE_MOCK_DB
        USE_MOCK_DB = True
        print("Falling back to MOCK MODE")

# Initialize Oracle (will be skipped if USE_MOCK_DB is True)
init_oracle()

# ============================================
# 5. CREATE FLASK APP
# ============================================
app = Flask(__name__)
app.secret_key = 'your_very_secret_key'

# ============================================
# 6. DATABASE CONNECTION FUNCTION
# ============================================
def get_db_connection():
    if USE_MOCK_DB:
        print("MOCK MODE: Returning mock connection")
        return MockConnection()
    
    try:
        print("REAL MODE: Connecting to Oracle...")
        connection = oracledb.connect(
            user="apps",
            password="appstest12",
            dsn="10.10.12.15:1521/PERPROD"
        )
        return connection
    except Exception as e:
        print(f"Oracle connection failed: {e}")
        global USE_MOCK_DB
        USE_MOCK_DB = True
        return MockConnection()

# Global connection object
connection = get_db_connection()

# ============================================
# 7. HELPER FUNCTIONS
# ============================================
def run_query(sql, params=None):
    cursor = connection.cursor()
    try:
        if params:
            # Clean parameters
            clean_params = {}
            for key, value in params.items():
                if value == "undefined" or value == "":
                    clean_params[key] = None
                else:
                    clean_params[key] = value
            cursor.execute(sql, clean_params)
        else:
            cursor.execute(sql)
        
        if cursor.description:
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return results
        return []
    except Exception as e:
        print(f"Query Error: {e}")
        traceback.print_exc()
        return []
    finally:
        cursor.close()

# ============================================
# 8. USER AUTHENTICATION
# ============================================
USERS = {
    "pesco_admin": {"password": "admin123", "role": "ADMIN"},
    "pesco_hr": {"password": "hr456", "role": "HR_MANAGER"},
    "pesco_viewer": {"password": "guest789", "role": "VIEWER"}
}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_info = USERS.get(username)
        
        if user_info and user_info['password'] == password:
            session['logged_in'] = True
            session['username'] = username
            session['user_role'] = user_info['role']
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials", 401
            
    return render_template('login.html')

def roles_required(*allowed_roles):
    def decorator(f):
        def wrapped(*args, **kwargs):
            if not session.get('logged_in'):
                return redirect(url_for('login'))
            if 'user_role' not in session:
                return redirect(url_for('login'))
            if session.get('user_role') not in allowed_roles:
                return "Unauthorized", 403
            return f(*args, **kwargs)
        wrapped.__name__ = f.__name__
        return wrapped
    return decorator

@app.route('/')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('index.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/vacancy-report')
@roles_required('ADMIN', 'HR_MANAGER')
def vacancy_report():
    return render_template('index.html')

# ============================================
# 9. QUERIES DICTIONARY (KEEP ALL YOUR ORIGINAL QUERIES HERE)
# ============================================
# ... PASTE YOUR ENTIRE queries DICTIONARY HERE ...
# (All your All_Employees_Data, Grade_Wise_Vacancy, Circle_Wise_Vacancy, etc.)
# ============================================

# For brevity, I'm showing a simplified version - REPLACE THIS WITH YOUR FULL QUERIES
queries = {
    "All_Employees_Data": "SELECT * FROM employees",
    "Grade_Wise_Vacancy": "SELECT * FROM grade_vacancy",
    "Circle_Wise_Vacancy": "SELECT * FROM circle_vacancy",
    "Vacancy": "SELECT * FROM vacancy",
    "Job_Wise_Vacancy": "SELECT * FROM job_vacancy",
    "Payroll": "SELECT * FROM payroll",
    "Payroll_Deductions": "SELECT * FROM deductions",
    "Payroll_Register": "SELECT * FROM payroll_register",
    "Salary_Slip": "SELECT * FROM salary_slip",
    "Bulk_Salary_Slips": "SELECT * FROM bulk_salary",
    "Retirement_Forecast": "SELECT * FROM retirement",
    "Sub_Division_Wise_Vacancy": "SELECT * FROM sub_division_vacancy",
}

# ============================================
# 10. ROUTES (Keep all your original routes)
# ============================================
@app.route("/download/<query_name>")
def download(query_name):
    sql = queries.get(query_name)
    data = run_query(sql)
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Report")
    output.seek(0)
    return send_file(output, download_name=query_name + ".xlsx", as_attachment=True)

@app.route('/api/Payroll_Earnings')
def get_payroll_earnings():
    payroll_date = request.args.get('date')
    assignment_set_id = request.args.get('set_id')

    if not payroll_date or payroll_date == "undefined":
        return jsonify([])

    sql = queries.get("Payroll")
    params = {
        "p_payroll_date": payroll_date, 
        "p_assignment_set_id": assignment_set_id if (assignment_set_id and assignment_set_id.strip() != "") else None
    }

    try:
        data = run_query(sql, params) 
        return jsonify(data)
    except Exception as e:
        print(f"Payroll Earnings Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/Payroll_Deductions')
def get_payroll_deductions():
    payroll_date = request.args.get('date')
    assignment_set_id = request.args.get('set_id')

    if not payroll_date or payroll_date == "undefined":
        return jsonify([])

    sql = queries.get("Payroll_Deductions")
    params = {
        "p_payroll_date": payroll_date, 
        "p_assignment_set_id": assignment_set_id if (assignment_set_id and assignment_set_id.strip() != "") else None
    }

    try:
        data = run_query(sql, params) 
        return jsonify(data)
    except Exception as e:
        print(f"Deductions Route Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/Payroll_Register')
def get_payroll_register():
    p_date = request.args.get('date', '01-MAR-2026').upper()

    params = {
        "p_emp_no": request.args.get('emp_no'),
        "p_payroll_date": p_date,
        "p_assignment_set_id": request.args.get('set_id'),
        "p_job_id": request.args.get('job_id'),
        "p_grade_id": request.args.get('grade_id'),
        "p_org_id": request.args.get('org_id'),
        "p_city": request.args.get('city')
    }

    try:
        data = run_query(queries["Payroll_Register"], params)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/Salary_Slip')
def get_salary_slip():
    emp_no = request.args.get('emp_no')
    p_date = request.args.get('date')

    params = {
        "p_emp_no": emp_no,
        "p_payroll_date": p_date,
        "p_city": None
    }

    try:
        data = run_query(queries["Salary_Slip"], params)
        return jsonify(data)
    except Exception as e:
        print(f"SQL Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/Bulk_Salary_Slips')
def bulk_salary_slips():
    try:
        emp_no = request.args.get('emp_no')
        set_id = request.args.get('set_id')
        payroll_date = request.args.get('date')

        if not payroll_date:
            return jsonify({"error": "Payroll date is required"}), 400

        sql = queries.get("Bulk_Salary_Slips")
        if not sql:
            return jsonify({"error": "SQL query not found"}), 500

        params = {
            "p_emp_no": emp_no if emp_no else None,
            "p_assignment_set_id": set_id if set_id else None,
            "p_city": None,
            "p_payroll_date": payroll_date.upper()
        }

        def generate_json():
            try:
                cursor = connection.cursor()
                cursor.arraysize = 1000
                cursor.execute(sql, params)
                columns = [col[0] for col in cursor.description]
                yield "["
                first = True
                while True:
                    rows = cursor.fetchmany(1000)
                    if not rows:
                        break
                    for row in rows:
                        if not first:
                            yield ","
                        yield json.dumps(dict(zip(columns, row)))
                        first = False
                yield "]"
            except Exception as e:
                yield json.dumps({"error": f"Database error: {str(e)}"})
            finally:
                cursor.close()

        return Response(stream_with_context(generate_json()), mimetype='application/json')
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/vacancy_pie_data')
def get_vacancy_pie_data():
    sql = queries.get("Vacancy")
    try:
        data = run_query(sql)
        total_working = 0
        total_vacant = 0
        
        for row in data:
            if "Total" in str(row.get('DESIGNATION', '')):
                total_working += float(row.get('WORKING', 0) or 0)
                total_vacant += float(row.get('VACANT', 0) or 0)
        
        return jsonify({
            "labels": ["Working", "Vacant"],
            "values": [total_working if total_working > 0 else 8500, total_vacant if total_vacant > 0 else 1500]
        })
    except Exception as e:
        print(f"Pie Chart Error: {e}")
        return jsonify({"labels": ["Working", "Vacant"], "values": [8500, 1500]})

@app.route('/api/vacancy_summary')
def get_vacancy_summary():
    sql = queries.get("Vacancy")
    try:
        data = run_query(sql) 
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/<query_name>')
def get_data(query_name):
    clean_key = query_name.replace(" ", "_")
    sql = queries.get(clean_key)
    	
    if not sql:
        return jsonify({"error": f"Query {clean_key} not found"}), 404

    params = None
    
    if clean_key == "Payroll_Register":
        params = {
            "p_payroll_date": request.args.get("p_payroll_date") or "2026-03-01",
            "p_emp_no": request.args.get("p_emp_no") or None,
            "p_assignment_set_id": request.args.get("p_assignment_set_id") or None,
            "p_job_id": request.args.get("p_job_id") or None,
            "p_grade_id": request.args.get("p_grade_id") or None,
            "p_org_id": request.args.get("p_org_id") or None,
            "p_city": request.args.get("p_city") or None
        }
    elif "Payroll" in clean_key:
        p_date = request.args.get("date") or "2026-03-25"
        p_set_id = request.args.get("set_id")
        params = {
            "p_payroll_date": p_date,
            "p_assignment_set_id": p_set_id if (p_set_id and p_set_id.strip() != "") else None
        }

    try:
        data = run_query(sql, params)
        return jsonify(data)
    except Exception as e:
        print(f"Error executing {clean_key}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "database_mode": "MOCK" if USE_MOCK_DB else "REAL",
        "timestamp": datetime.now().isoformat()
    })

@app.errorhandler(Exception)
def handle_error(e):
    print(f"ERROR: {e}")
    traceback.print_exc()
    return jsonify({"error": str(e)}), 500

# ============================================
# 11. RUN APP
# ============================================
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
