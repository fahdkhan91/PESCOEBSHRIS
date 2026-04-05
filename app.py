from flask import Flask, jsonify, render_template, request, url_for, session, redirect, stream_with_context, request, Response
from flask import send_file, render_template_string
import pandas as pd
from io import BytesIO
from datetime import datetime
import oracledb
import io
import os
import platform
import json

USE_MOCK_DB = True  # Set to False for real Oracle, True for Render deployment

# Mock Database Classes (only used when USE_MOCK_DB = True)
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
        # Return sample data for any query when in mock mode
        if not hasattr(self, '_called'):
            self.description = [('COL1',), ('COL2',)]
            self.results = [('Mock Data', 'Running in Mock Mode')]
            self._called = True
        return self
    
    def fetchall(self):
        return self.results
    
    def fetchmany(self, size):
        return self.results[:size]
    
    def fetchone(self):
        return self.results[0] if self.results else None
    
    def close(self):
        pass

# Modify get_db_connection to support mock mode
original_get_db_connection = None

# Store original if it exists
try:
    original_get_db_connection = get_db_connection
except:
    pass

def get_db_connection():
    if USE_MOCK_DB:
        return MockConnection()
    try:
        import oracledb
        return oracledb.connect(
            user="apps",
            password="appstest12",
            dsn="10.10.12.15:1521/PERPROD"
        )
    except:
        return MockConnection()

# Also modify init_oracle to skip when in mock mode
original_init_oracle = None
try:
    original_init_oracle = init_oracle
except:
    pass

def init_oracle():
    if USE_MOCK_DB:
        print("Mock mode - skipping Oracle init")
        return
    if original_init_oracle:
        original_init_oracle()
    else:
        try:
            import oracledb
            if platform.system() == "Linux":
                lib_dir = os.path.join(os.getcwd(), "instantclient")
                oracledb.init_oracle_client(lib_dir=lib_dir)
            else:
                oracledb.init_oracle_client(lib_dir=r"C:\oracle\instantclient_23_0")
        except:
            pass

print(f"=== RUNNING IN {'MOCK' if USE_MOCK_DB else 'REAL'} MODE ===")
# ============================================
# END OF ADDED BLOCK - YOUR ORIGINAL CODE CONTINUES BELOW
@app.route("/download_pdf/<query_name>")
def download_pdf(query_name):

    html_table = df.to_html(classes='table table-striped', index=False)

    from svglib.svglib import svg2rlg


@app.route("/download/<query_name>")
def download(query_name):

    sql = queries.get(query_name)

    data = run_query(sql)

    df = pd.DataFrame(data)

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Report")

    output.seek(0)

    return send_file(
        output,
        download_name=query_name + ".xlsx",
        as_attachment=True
    )


USERS = {
    "pesco_admin": {"password": "admin123", "role": "ADMIN"}, # <--- MUST HAVE COMMA HERE
    "pesco_hr": {"password": "hr456", "role": "HR_MANAGER"},    # <--- MUST HAVE COMMA HERE
    "pesco_viewer": {"password": "guest789", "role": "VIEWER"}
}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check if username exists and password matches
        user_info = USERS.get(username)
        
        if user_info and user_info['password'] == password:
            session['logged_in'] = True
            session['username'] = username
            session['user_role'] = user_info['role']  # <--- SAVE THE ROLE HERE
            return redirect(url_for('dashboard'))
        else:
            return "Invalid credentials", 401
            
    return render_template('login.html')

def roles_required(*allowed_roles):
    if session.get('user_role') not in allowed_roles:
        return False
    return True



@app.route('/vacancy-report')
def vacancy_report():
    if not roles_required('ADMIN', 'HR_MANAGER'):
        return "Unauthorized", 403
    # ... your existing code ...

@app.route('/')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    return render_template('index.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/api/Payroll_Earnings')
def get_payroll_earnings():
    # 1. Get values from the URL
    payroll_date = request.args.get('date')
    assignment_set_id = request.args.get('set_id')

    # 2. Validation: Prevent crash if date is missing or undefined
    if not payroll_date or payroll_date == "undefined":
        return jsonify([])

    # 3. SQL Query (Cleaned: No grouping sets, no CASE total)
    sql = """
    SELECT 
        petf.element_name AS earning_head,
        SUM(NVL(prrv.result_value, 0)) AS Total
    FROM pay_payroll_actions ppa
    JOIN pay_assignment_actions paa ON paa.payroll_action_id = ppa.payroll_action_id
    JOIN pay_run_results prr ON prr.assignment_action_id = paa.assignment_action_id
    JOIN pay_run_result_values prrv ON prrv.run_result_id = prr.run_result_id
    JOIN pay_input_values_f pivf ON pivf.input_value_id = prrv.input_value_id
    JOIN pay_element_types_f petf ON prr.element_type_id = petf.element_type_id
    JOIN pay_element_classifications pec ON petf.classification_id = pec.classification_id
    WHERE pivf.name = 'Pay Value'
        AND petf.business_group_id = 81
        AND ppa.date_earned = TO_DATE(:p_payroll_date, 'YYYY-MM-DD')
        AND ppa.assignment_set_id = NVL(:p_assignment_set_id, ppa.assignment_set_id)
        AND pec.classification_name NOT LIKE '%Deduction%'
    GROUP BY petf.element_name
    ORDER BY petf.element_name
    """
    
    # 4. Dictionary: Mapping Python variables to SQL :variables
    params = {
        "p_payroll_date": payroll_date, 
        "p_assignment_set_id": assignment_set_id if (assignment_set_id and assignment_set_id.strip() != "") else None
    }

    # 5. Execute and Return
    try:
        data = run_query(sql, params) 
        return jsonify(data)
    except Exception as e:
        print(f"Payroll Earnings Error: {e}")
        return jsonify({"error": str(e)}), 500
queries = {

"All_Employees_Data": """
       SELECT 
    pp.employee_number as "A.ERP No",
    pp.first_name || ' ' || pp.middle_names || ' ' || pp.last_name as "B.Name",
    pp.attribute10 as "C.Father Name",
    pp.national_identifier as "Cnic",
    TO_CHAR(pp.date_of_birth, 'DD-MM-YYYY') as "Date of Birth",
    
    /* New Retirement Forecast Column */
    TO_CHAR(ADD_MONTHS(pp.date_of_birth, 60 * 12), 'DD-MM-YYYY') as "Retirement Forecast",
    
    gr.name as "Grade",
    jb.name as "Designation",
    ass.ass_attribute1 as "E.Cadre",
    ass.ass_attribute6 as "Sanctioned Scale",
    TO_CHAR(ass.effective_start_date, 'DD-MM-YYYY') as "H.Current Posting Date",
    org.name as "D.Office Name",
    
    CASE
        WHEN ass.employment_category='REG' THEN 'Regular'
        WHEN ass.employment_category='CONSLSM' THEN 'Lumpsum'
        WHEN ass.employment_category='COT' THEN 'Contract'
        WHEN ass.employment_category='XX_DEP' THEN 'Deputationist'
        WHEN ass.employment_category='DW' THEN 'Daily Wages'
    END AS "Employee Category"
FROM per_people_v7 pp
INNER JOIN per_assignments_x ass ON pp.employee_number = ass.assignment_number
INNER JOIN per_all_organization_units org ON ass.organization_id = org.organization_id
INNER JOIN per_jobs jb ON ass.job_id = jb.job_id
INNER JOIN per_grades gr ON ass.grade_id = gr.grade_id

WHERE ass.location_id <> '27625'
    """,
"Grade_Wise_Vacancy": """
WITH position_data AS (
    SELECT 
        grade.grade_id,
        grade.name AS A_GRADE,
        SUM(pos.max_persons) AS sanctioned
    FROM per_grades grade 
    JOIN   hr.hr_all_positions_f#   pos
      ON TRIM(UPPER(grade.name)) = TRIM(UPPER(pos.attribute6))
    WHERE NVL(pos.location_id, -1) <> 27625
      AND SYSDATE BETWEEN pos.effective_start_date AND pos.effective_end_date
    GROUP BY  grade.grade_id,grade.name
ORDER BY grade.name
),

assignment_data AS (
    SELECT 
        ass.grade_id,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'REG' THEN 1 ELSE 0 END) AS regular,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'COT' THEN 1 ELSE 0 END) AS contract,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'CONSLSM' THEN 1 ELSE 0 END) AS lumpsum,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'XX_DEP' THEN 1 ELSE 0 END) AS deputation,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'DW' THEN 1 ELSE 0 END) AS daily_wages
    FROM per_assignments_x ass
    WHERE NVL(ass.location_id, -1) <> 27625
      AND ass.primary_flag = 'Y'
      AND ass.assignment_type = 'E'
      AND SYSDATE BETWEEN ass.effective_start_date AND ass.effective_end_date
    GROUP BY ass.grade_id
)

SELECT 
    p.A_GRADE,
    p.sanctioned,
    NVL(a.regular, 0) AS regular,
    NVL(a.contract, 0) AS contract,
    NVL(a.lumpsum, 0) AS lumpsum,
    NVL(a.deputation, 0) AS deputation,
    NVL(a.daily_wages, 0) AS daily_wages,

    NVL(a.regular, 0)
  + NVL(a.contract, 0)
  + NVL(a.lumpsum, 0)
  + NVL(a.deputation, 0)
  + NVL(a.daily_wages, 0) AS working,

    GREATEST(
        p.sanctioned -
        ( NVL(a.regular, 0)
        + NVL(a.contract, 0)
        + NVL(a.lumpsum, 0)
        + NVL(a.deputation, 0)
        + NVL(a.daily_wages, 0) ),
        0
    ) AS vacant

FROM position_data p
LEFT JOIN assignment_data a
    ON p.grade_id = a.grade_id
ORDER BY p.A_GRADE,p.grade_id

""",

"Circle_Wise_Vacancy": """
WITH base_circles AS (
    -- Your 11 primary Circles
    SELECT organization_id, name AS circle_name
    FROM hr_all_organization_units
    WHERE organization_id IN ('101', '1104', '1107', '1105', '794', '1684', '503', '821', '1670', '1604', '1073')
),

-- 1. Build Recursive Hierarchy for the 11 Circles
org_tree (circle_id, child_org_id, circle_name) AS (
    SELECT c.organization_id, c.organization_id, c.circle_name
    FROM base_circles c
    UNION ALL
    SELECT ot.circle_id, pose.organization_id_child, ot.circle_name
    FROM org_tree ot
    JOIN per_org_structure_elements pose ON pose.organization_id_parent = ot.child_org_id
),

-- 2. Unique Mapping (Assigns each Org to only ONE Circle or Head Quarter)
unique_mapping AS (
    SELECT org_id, circle_name FROM (
        SELECT child_org_id AS org_id, circle_name, 
               ROW_NUMBER() OVER (PARTITION BY child_org_id ORDER BY circle_id) as rnk
        FROM org_tree
    ) WHERE rnk = 1
    
    UNION ALL
    
    -- UNION with all offices having location_id = 25468 (Head Quarter)
    SELECT organization_id, 'Head Quarter'
    FROM hr_all_organization_units
    WHERE location_id = '25468'
      AND organization_id NOT IN (SELECT child_org_id FROM org_tree)
),

-- 3. Position Data (Sanctioned count only)
position_stats AS (
    SELECT 
        pos.organization_id,
        SUM(NVL(pos.max_persons, 0)) as sanctioned
    FROM hr.hr_all_positions_f pos
    WHERE TRUNC(SYSDATE) BETWEEN pos.effective_start_date AND pos.effective_end_date
      AND (NVL(pos.location_id, -1) <> 27625 OR pos.location_id = '25468')
    GROUP BY pos.organization_id
),

-- 4. Assignment Data (Working count only)
assignment_stats AS (
    SELECT 
        ass.organization_id,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'REG' THEN 1 ELSE 0 END) AS regular,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'COT' THEN 1 ELSE 0 END) AS contract,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'CONSLSM' THEN 1 ELSE 0 END) AS lumpsum,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'XX_DEP' THEN 1 ELSE 0 END) AS deputation,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'DW' THEN 1 ELSE 0 END) AS daily_wages
    FROM per_assignments_x ass
    WHERE ass.primary_flag = 'Y'
      AND TRUNC(SYSDATE) BETWEEN ass.effective_start_date AND ass.effective_end_date
      AND (NVL(ass.location_id, -1) <> 27625 OR ass.location_id = '25468')
    GROUP BY ass.organization_id
)

-- 5. Final Circle-Wise Rollup with Vacant = Sanctioned - Working
SELECT
    um.circle_name AS "Circle Name",
    SUM(NVL(ps.sanctioned, 0)) AS "Total Sanctioned",
    
    -- Sum of all working categories
    (SUM(NVL(asst.regular, 0)) + SUM(NVL(asst.contract, 0)) + SUM(NVL(asst.lumpsum, 0)) + 
     SUM(NVL(asst.deputation, 0)) + SUM(NVL(asst.daily_wages, 0))) AS "Total Working",
    
    -- Strict Vacant Rule: Sanctioned - Working
    GREATEST(
        SUM(NVL(ps.sanctioned, 0)) - 
        (SUM(NVL(asst.regular, 0)) + SUM(NVL(asst.contract, 0)) + SUM(NVL(asst.lumpsum, 0)) + 
         SUM(NVL(asst.deputation, 0)) + SUM(NVL(asst.daily_wages, 0))),
        0
    ) AS "Total Vacant"

FROM unique_mapping um
LEFT JOIN position_stats ps ON um.org_id = ps.organization_id
LEFT JOIN assignment_stats asst ON um.org_id = asst.organization_id
GROUP BY um.circle_name
ORDER BY CASE WHEN um.circle_name = 'Head Quarter' THEN 0 ELSE 1 END, um.circle_name
""",

"Vacancy":r"""

WITH
  /* ================= SCALE 17 BASE DATA ================= */
  s17_position_data AS
  (SELECT pos.position_id,
    pos.organization_id,
    pos.name   AS position_name,
    pos.max_persons AS sanctioned
  FROM hr.hr_all_positions_f pos
  JOIN per_jobs_vl job
  ON pos.job_id = job.job_id
  JOIN per_valid_grades_v vld
  ON job.job_id = vld.job_id
  WHERE NVL(pos.location_id, -1) <> 27625
  AND TO_NUMBER(REGEXP_SUBSTR(vld.name, '\d+')) = 17
  ),
  s17_assignment_data AS
  (SELECT position_id,
    COUNT(*) AS working
  FROM per_assignments_x
  WHERE NVL(location_id, -1) <> 27625
  GROUP BY position_id
  ),
  s17_excluded_positions AS
  (
  SELECT DISTINCT position_id
FROM s17_position_data
WHERE 
    position_name LIKE '%Revenue%' OR
    position_name LIKE '%Chief Commercial%' OR
    position_name LIKE '%GIS%' OR
    position_name LIKE '%HR%' OR
    position_name LIKE '%L&L%' OR
    position_name LIKE '%Confidential%' OR
    position_name LIKE '%PCC%' OR
    position_name LIKE '%MM Directorate%' OR
    position_name LIKE '%Marketing%' OR
    position_name LIKE '%Tariff%' OR
    position_name LIKE '%Transport%' OR
    position_name LIKE '%PR%' OR
    position_name LIKE '%MIS%' OR
    position_name LIKE '%Store%' OR
    position_name LIKE '%Account%' OR   position_name LIKE '%Accounts%' or
    position_name LIKE '%Audit%' OR
    position_name LIKE '%(Social Impact)%' OR
    position_name LIKE '%Enviro%' OR
    position_name LIKE '%P/SA%' OR
    position_name LIKE '%CISA%' OR
    position_name LIKE '%Computer%' OR
    position_name LIKE '%Web Master%' OR
    (position_name LIKE '%Network%' AND position_name LIKE '%IT%') OR
    position_name LIKE '%Database%' OR
    position_name LIKE '%Quality Assurance%' OR
    (position_name LIKE '%Application%' AND (position_name LIKE '%ERP%' OR position_name LIKE '%Billing%')) OR
    (position_name LIKE '%Business Analyst%' AND (position_name LIKE '%ERP%' OR position_name LIKE '%Billing%')) OR
    position_name LIKE '%Civil Works%' OR
    (position_name LIKE '%MIRAD%' AND (
        position_name LIKE '%Demand Forecasting%' OR
        position_name LIKE '%Contract Management%' OR
        position_name LIKE '%Regulatory%' OR
        position_name LIKE '%Finance%' OR
        position_name LIKE '%Transmission%' OR
        position_name LIKE '%Admin%'or position_name LIKE '%MIS%'
    ))
    ),
  /* ================= INDIVIDUAL ROW MAPPING - SCALE 17 ================= */
  s17_row1 AS
  (SELECT 'SDOs / Assistant Managers' AS designation,
    SUM(p.sanctioned)                 AS sanctioned,
    NVL(SUM(a.working), 0)            AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_id NOT IN
    (SELECT position_id FROM s17_excluded_positions
    )
  ),
  s17_row2 AS
  (SELECT 'Asstt: Managers (Revenue)/(Commercial)' AS designation,
    SUM(p.sanctioned)                              AS sanctioned,
    NVL(SUM(a.working), 0)                         AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Revenue%'
  OR p.position_name LIKE '%Chief Commercial%'
  ),
  s17_row3 AS
  (SELECT 'Asstt: GIS Specialist' AS designation,
    SUM(p.sanctioned)             AS sanctioned,
    NVL(SUM(a.working), 0)        AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%GIS%'
  ),
  s17_row4 AS
  (SELECT 'AMs (HR)/ ( PR)' AS designation,
    SUM(p.sanctioned)       AS sanctioned,
    NVL(SUM(a.working), 0)  AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
 WHERE p.position_name LIKE '%Assistant Manager-Confidential%'
  OR p.position_name like '%Assistant Manager-PR Office%'
OR p.position_name like '%Assistant Manager(HR/Admin)-PESCO Head Quarter HR Directorate%'
OR p.position_name like '%Assistant Manager-Training & Development%'
or p.position_name like '%Assistant Manager(L&L)-Chief Law Office%' 
or p.position_name like '%Assistant Manager(Transport)-Admin & Services%'
or p.position_name like '%Assistant Manager (MIS)-PESCO Head Quarter HR Directorate%'
  ),
  s17_row5 AS
  (SELECT 'Asstt: Managers (Field Stores)/H/Q' AS designation,
    SUM(p.sanctioned)                          AS sanctioned,
    NVL(SUM(a.working), 0)                     AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Assistant Manager-Field Store%'or p.position_name LIKE '%MM Directorate%'
  ),
  s17_row6 AS
  (SELECT 'AM (C/Accounts)' AS designation,
    SUM(p.sanctioned)       AS sanctioned,
    NVL(SUM(a.working), 0)  AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Account%'
  ),
  s17_row7 AS
  (SELECT 'Asstt: Manager (Audit)' AS designation,
    SUM(p.sanctioned)              AS sanctioned,
    NVL(SUM(a.working), 0)         AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Audit%'
  ),
  s17_row8 AS
  (SELECT 'Asstt: Managers (Social Impact) /Enviroment' AS designation,
    SUM(p.sanctioned)                                   AS sanctioned,
    NVL(SUM(a.working), 0)                              AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%(Social Impact)%'
  or p.position_name LIKE '%Enviroment%'
  ),
  s17_row9 AS
  (SELECT 'AMs (PSA/CO) / AD (CISA) MIS' AS designation,
    SUM(p.sanctioned)                    AS sanctioned,
    NVL(SUM(a.working), 0)               AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%P/SA%'
  OR p.position_name LIKE '%CISA%'
  OR p.position_name LIKE '%Computer%'
  OR p.position_name LIKE '%PCC%'
  ),
 s17_row10 AS
  (SELECT 'Web Master - IT Operation' AS designation,
    1 AS sanctioned,
    NVL(SUM(a.working), 0) AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Web Master%'
  ),
  s17_row11 AS
  (SELECT 'AM (Networks) - IT Operation' AS designation,
    SUM(p.sanctioned)                    AS sanctioned,
    NVL(SUM(a.working), 0)               AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE (p.position_name LIKE '%Network%') and (p.position_name LIKE '%IT%')
  ),
  s17_row12 AS
  (SELECT 'AM Database Administration - IT Operation' AS designation,
    SUM(p.sanctioned)                                 AS sanctioned,
    NVL(SUM(a.working), 0)                            AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Database%'
  ),
  s17_row13 AS
  (SELECT 'AM Quality Assurance & System Audit - IT' AS designation,
    1                          AS sanctioned,
    NVL(SUM(a.working), 0)                           AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Quality Assurance%'
  ),
  s17_row14 AS
  (SELECT 'AM Application Development - ERP - IT Opr' AS designation,
    SUM(p.sanctioned)                                 AS sanctioned,
    NVL(SUM(a.working), 0)                            AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Application%'
  AND p.position_name LIKE '%ERP%'
  ),
  s17_row15 AS
  (SELECT 'AM Application Dev: - Billing & CCB - IT Opr' AS designation,
    2                                   AS sanctioned,
    NVL(SUM(a.working), 0)                               AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Application%'
  AND p.position_name LIKE '%Billing%'
  ),
  s17_row16 AS
  (SELECT 'Business Analyst - ERP - IT Operation' AS designation,
    2                   AS sanctioned,
    NVL(SUM(a.working), 0)                        AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Business Analyst%'
  AND p.position_name LIKE '%ERP%'
  ),
  s17_row17 AS
  (SELECT 'Business Analyst - Billing & CCB - IT Opr' AS designation,
    2                                AS sanctioned,
    NVL(SUM(a.working), 0)                            AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Business Analyst%'
  AND p.position_name LIKE '%Billing%'
  ),
  s17_row18 AS
  (SELECT 'AM (Civil) Works' AS designation,
    SUM(p.sanctioned)        AS sanctioned,
    NVL(SUM(a.working), 0)   AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Civil Works%'
  ),
  s17_row19 AS
  (SELECT 'AM (Demand Forecasting) MIRAD' AS designation,
    2                     AS sanctioned,
    NVL(SUM(a.working), 0)                AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Demand Forecasting%'
  AND p.position_name LIKE '%MIRAD%'
  ),
  s17_row20 AS
  (SELECT 'AM (Contract Management) MIRAD' AS designation,
    SUM(p.sanctioned)                      AS sanctioned,
    NVL(SUM(a.working), 0)                 AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Contract Management%'
  AND p.position_name LIKE '%MIRAD%'
  ),
  s17_row21 AS
  (SELECT 'AM (Regulatory Affairs) MIRAD' AS designation,
    SUM(p.sanctioned)                     AS sanctioned,
    NVL(SUM(a.working), 0)                AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Regulatory%'
  AND p.position_name LIKE '%MIRAD%'
  ),
  s17_row22 AS
  (SELECT 'AM (Finance) MIRAD' AS designation,
    2          AS sanctioned,
    NVL(SUM(a.working), 0)     AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Finance%'
  AND p.position_name LIKE '%MIRAD%'
  ),
  s17_row23 AS
  (SELECT 'AM (Transmission Planning) MIRAD' AS designation,
    SUM(p.sanctioned)                        AS sanctioned,
    NVL(SUM(a.working), 0)                   AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Transmission%'
  AND p.position_name LIKE '%MIRAD%'
  ),
  s17_row24 AS
  (SELECT 'Assistant Manager (Admin) MIRAD' AS designation,
    SUM(p.sanctioned)                      AS sanctioned,
    NVL(SUM(a.working), 0)                 AS working
  FROM s17_position_data p
  LEFT JOIN s17_assignment_data a
  ON p.position_id = a.position_id
  WHERE p.position_name LIKE '%Admin%'
  AND p.position_name LIKE '%MIRAD%'
  ),
  s17_combined AS
  (SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working) AS vacant,
    0 AS surplus
  FROM s17_row1 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row2 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row3 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row4 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row5 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row6 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row7 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row8 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row9 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row10 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row11 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row12 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row13 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row14 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row15 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row16 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row17 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row18 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row19 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row20 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row21 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row22 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row23 t
  UNION ALL
  SELECT '17' AS scale, t.designation,
    t.sanctioned,
    t.working,
    (t.sanctioned - t.working),
    0
  FROM s17_row24 t
  ),
  
/* 1. DATA SOURCES - SCALE 18 */
s18_position_data AS (
    SELECT pos.position_id, pos.name AS position_name, job.name AS group_designation, pos.organization_id, pos.max_persons AS sanctioned
    FROM hr.hr_all_positions_f pos
    JOIN per_jobs_vl job ON pos.job_id = job.job_id
    WHERE NVL(pos.location_id, -1) <> 27625
      AND EXISTS (SELECT 1 FROM per_valid_grades_v vld WHERE vld.job_id = job.job_id AND TO_NUMBER(REGEXP_SUBSTR(vld.name, '\d+')) = 18)
),
s18_assignment_data AS (
    SELECT position_id, COUNT(*) AS working
    FROM per_assignments_x
    WHERE NVL(location_id, -1) <> 27625
    GROUP BY position_id
),

/* SAME EXCLUSION LIST FOR SCALE 18 */
s18_excluded_positions AS (
    SELECT DISTINCT position_id
    FROM s18_position_data
    WHERE 
        position_name LIKE '%Revenue%' OR
        position_name LIKE '%Chief Commercial%' OR
        position_name LIKE '%GIS%' OR        
        position_name LIKE '%L&L%' OR
        position_name LIKE '%PSST%' OR        
        position_name LIKE '%Confidential%' OR
        position_name LIKE '%PCC%' OR
        position_name LIKE '%MM Directorate%' OR
        position_name LIKE '%Marketing%' OR
        position_name LIKE '%Tariff%' OR
        position_name LIKE '%Transport%' OR
        position_name LIKE '%PR%' OR
        position_name LIKE '%MIS%' OR
        position_name LIKE '%Store%' OR
        position_name LIKE '%Account%' OR position_name LIKE '%Accounts%' OR
        position_name LIKE '%Audit%' OR
        position_name LIKE '%(Social Impact)%' OR
        position_name LIKE '%Enviro%' OR
        position_name LIKE '%Safeguard%' OR
        position_name LIKE '%P/SA%' OR
        position_name LIKE '%CISA%' OR
        position_name LIKE '%Computer%' OR
        position_name LIKE '%Web Master%' OR
        (position_name LIKE '%Network%' AND position_name LIKE '%IT%') OR
        position_name LIKE '%Database%' OR
        position_name LIKE '%Quality Assurance%' OR
        (position_name LIKE '%Application%' AND (position_name LIKE '%ERP%' OR position_name LIKE '%Billing%')) OR
        (position_name LIKE '%Business Analyst%' AND (position_name LIKE '%ERP%' OR position_name LIKE '%Billing%')) OR
        position_name LIKE '%Civil Works%' OR
        (position_name LIKE '%MIRAD%' AND (
            position_name LIKE '%Demand Forecasting%' OR
            position_name LIKE '%Contract Management%' OR
            position_name LIKE '%Regulatory%' OR
            position_name LIKE '%Finance%' OR
            position_name LIKE '%Transmission%' OR
            position_name LIKE '%Admin%' OR position_name LIKE '%MIS%'
        ))
),

/* 2. FILTER MAPPINGS */
s18_row2_ids AS (SELECT position_id FROM s18_position_data WHERE UPPER(group_designation) LIKE '%DEPUTY MANAGER%' AND (UPPER(position_name) LIKE '%CHIEF COMMERCIAL OFFICE%' OR UPPER(position_name) LIKE '%CUSTOMER SERVICES DIRECTORATE%')),
s18_row3_ids AS (SELECT position_id FROM s18_position_data WHERE (organization_id IN (SELECT organization_id FROM per_organization_units WHERE name IN ('Chief Law Office','Confidential','Training & Development','Transport Department','HRM','PESCO Head Quarter HR Directorate')) AND (UPPER(position_name) LIKE '%DEPUTY MANAGER%' OR UPPER(position_name) LIKE '%HRM%'))),
s18_row4_ids AS (SELECT position_id FROM s18_position_data WHERE (UPPER(position_name) LIKE '%PROJECT%MANAGEMENT%UNIT%' OR UPPER(position_name) LIKE '%PROJECT%FINANCE%' OR UPPER(position_name) LIKE '%CORPORATE%ACCOUNT%') AND UPPER(group_designation) LIKE '%DEPUTY MANAGER%'),
s18_row5_ids AS (SELECT position_id FROM s18_position_data WHERE organization_id IN (SELECT organization_id FROM per_organization_units WHERE name LIKE 'MM%')),
s18_row6_ids AS (SELECT position_id FROM s18_position_data WHERE (UPPER(position_name) LIKE '%MIS PESCO HQ%' OR UPPER(position_name) LIKE '%IT DIRECTORATE%' OR UPPER(position_name) LIKE '%BUSINESS APPLICATION%' OR UPPER(position_name) LIKE '%ERP%' OR UPPER(position_name) LIKE '%DATABASE%' OR UPPER(position_name) LIKE '%NETWORKS%' OR UPPER(position_name) LIKE '%P/SA%') AND (UPPER(position_name) LIKE '%DEPUTY MANAGER%')),
s18_row7_ids AS (SELECT position_id FROM s18_position_data WHERE organization_id IN (SELECT organization_id FROM per_organization_units WHERE name LIKE '%Audit%')),
s18_row8_ids AS (SELECT position_id FROM s18_position_data WHERE UPPER(position_name) LIKE '%ENVIRONMENT%SAFEGUARD%' OR UPPER(position_name) LIKE '%DEPUTY MANAGER%SAFETY%'),
s18_row9_ids AS (SELECT position_id FROM s18_position_data WHERE UPPER(position_name) LIKE '%SECURITY%' OR UPPER(position_name) LIKE '%SECU%'),
s18_row10_ids AS (SELECT position_id FROM s18_position_data WHERE UPPER(position_name) LIKE '%GIS SPECIALIST%'),
s18_row11_ids AS (SELECT position_id FROM s18_position_data WHERE (UPPER(position_name) LIKE '%CIVIL%WORK%GC%' OR UPPER(position_name) LIKE 'XEN%CIVIL%') AND UPPER(position_name) LIKE '%PESHAWAR%'),
s18_row12_ids AS (SELECT position_id FROM s18_position_data WHERE UPPER(position_name) LIKE '%LEGAL%' AND organization_id IN (SELECT organization_id FROM per_organization_units WHERE name LIKE '%MIRAD%')),
s18_row13_ids AS (SELECT position_id FROM s18_position_data WHERE UPPER(position_name) LIKE '%FINANCE%' AND organization_id IN (SELECT organization_id FROM per_organization_units WHERE name LIKE '%MIRAD%')),
s18_row14_ids AS (SELECT position_id FROM s18_position_data WHERE UPPER(position_name) LIKE '%TRANSMISSION PLANNING%' AND organization_id IN (SELECT organization_id FROM per_organization_units WHERE name LIKE '%MIRAD%')),
s18_row15_ids AS (SELECT position_id FROM s18_position_data WHERE UPPER(position_name) LIKE '%DEMAND FORECASTING%' AND organization_id IN (SELECT organization_id FROM per_organization_units WHERE name LIKE '%MIRAD%')),
s18_row16_ids AS (SELECT position_id FROM s18_position_data WHERE UPPER(position_name) LIKE '%REGULATORY AFFAIRS%' AND organization_id IN (SELECT organization_id FROM per_organization_units WHERE name LIKE '%MIRAD%')),
s18_row17_ids AS (SELECT position_id FROM s18_position_data WHERE UPPER(position_name) LIKE '%CONTRACT MANAGEMENT%' AND organization_id IN (SELECT organization_id FROM per_organization_units WHERE name LIKE '%MIRAD%')),
s18_dm_used_positions AS (
    SELECT DISTINCT position_id FROM (
        SELECT position_id FROM s18_row2_ids UNION ALL
        SELECT position_id FROM s18_row3_ids UNION ALL
        SELECT position_id FROM s18_row4_ids UNION ALL
        SELECT position_id FROM s18_row5_ids UNION ALL
        SELECT position_id FROM s18_row6_ids UNION ALL
        SELECT position_id FROM s18_row7_ids UNION ALL
        SELECT position_id FROM s18_row8_ids UNION ALL
        SELECT position_id FROM s18_row9_ids UNION ALL
        SELECT position_id FROM s18_row10_ids UNION ALL
        SELECT position_id FROM s18_row11_ids UNION ALL
        SELECT position_id FROM s18_row12_ids UNION ALL
        SELECT position_id FROM s18_row13_ids UNION ALL
        SELECT position_id FROM s18_row14_ids UNION ALL
        SELECT position_id FROM s18_row15_ids UNION ALL
        SELECT position_id FROM s18_row16_ids UNION ALL
        SELECT position_id FROM s18_row17_ids
    )
),
/* 3. ROW AGGREGATIONS - WITH EXCLUSION APPLIED TO ROW 1 */
s18_row1 AS (
    SELECT 'XENs / Dy. Managers' AS designation, 
           NVL(SUM(p.sanctioned), 0) AS sanctioned, 
           NVL(SUM(a.working), 0) AS working 
    FROM s18_position_data p 
    LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id 
    WHERE (p.group_designation LIKE 'XEN%' OR UPPER(p.group_designation) LIKE '%DEPUTY MANAGER%') 
      AND p.position_id NOT IN (SELECT position_id FROM s18_dm_used_positions)
      AND p.position_id NOT IN (SELECT position_id FROM s18_excluded_positions)
      AND p.sanctioned > 0
),
s18_row2 AS (SELECT 'DCMs / DM (CS)' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row2_ids)),
s18_row3 AS (SELECT 'DMs (HR)/(Services)/(Confdl:)/(L&L) / TPT' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row3_ids)),
s18_row4 AS (SELECT 'DM (C/Accounts) / Project Finance PMU' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row4_ids)),
s18_row5 AS (SELECT 'Dy. Manager (MM)' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row5_ids)),
s18_row6 AS (SELECT 'DM (MIS) / IT (Operations) /Business Applications' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row6_ids)),
s18_row7 AS (SELECT 'DM (Audit)' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row7_ids)),
s18_row8 AS (SELECT 'DM (Environment & Safeguard)' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row8_ids)),
s18_row9 AS (SELECT 'DM (Security)' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row9_ids)),
s18_row10 AS (SELECT 'Sr. GIS Specialist' AS designation, 1 AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row10_ids)),
s18_row11 AS (SELECT 'XEN/DM (Civil)' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row11_ids)),
s18_row12 AS (SELECT 'DM (Legal Contracts) MIRAD' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row12_ids)),
s18_row13 AS (SELECT 'DM (Finance) MIRAD' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row13_ids)),
s18_row14 AS (SELECT 'DM (Regulatory Affairs) MIRAD' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row16_ids)),
s18_row15 AS (SELECT 'DM (Contract Management) MIRAD' AS designation, NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working FROM s18_position_data p LEFT JOIN s18_assignment_data a ON p.position_id = a.position_id WHERE p.position_id IN (SELECT position_id FROM s18_row17_ids)),
/* 4. COMBINED RESULT & TOTALS */
s18_combined AS (
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working) AS vacant, 0 AS surplus FROM s18_row1 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row2 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row3 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row4 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row5 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row6 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row7 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row8 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row9 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row10 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row11 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row12 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row13 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row14 t UNION ALL
    SELECT '18' AS scale, t.designation, t.sanctioned, t.working, (t.sanctioned - t.working), 0 FROM s18_row15 t
),

/* --- SCALE 19 BASE DATA --- */
s19_assignment_data AS (SELECT position_id, COUNT(*) AS working FROM per_assignments_x WHERE NVL(location_id, -1) <> 27625 GROUP BY position_id),
s19_position_data AS (
    SELECT pos.position_id, pos.name AS position_name, job.name AS group_designation, pos.organization_id, pos.max_persons AS sanctioned
    FROM hr.hr_all_positions_f pos
    JOIN per_jobs_vl job ON pos.job_id = job.job_id
    WHERE NVL(pos.location_id, -1) <> 27625
      AND EXISTS (SELECT 1 FROM per_valid_grades_v vld WHERE vld.job_id = job.job_id AND REGEXP_LIKE(vld.name, '(^|[^0-9])19([^0-9]|$)'))
),

/* --- 2. ID MAPPINGS --- */
s19_exclusion_list AS (SELECT DISTINCT position_id FROM s19_position_data WHERE UPPER(position_name) LIKE '%ATTACHED%' OR UPPER(position_name) LIKE '%ON LEAVE%'OR UPPER(position_name) LIKE '%DIRECTOR%' OR UPPER(position_name) LIKE '%ACTING%' OR UPPER(position_name) LIKE '%MIS%'OR UPPER(position_name) LIKE '%ADDL DG%' OR UPPER(position_name) LIKE '%ATTACHED%'),
s19_row2_ids AS (SELECT position_id FROM s19_position_data WHERE position_name IN ('Manager(L&L)-Chief Law Office', 'Manager-Confidential', 'Manager(HRM)-PESCO Head Quarter HR Directorate', 'Manager(L&L)-PESCO Head Quarter HR Directorate', 'Manager-Training & Development')),
s19_row3_ids AS (SELECT position_id FROM s19_position_data WHERE UPPER(position_name) LIKE '%COMMERCIAL I%'),
s19_row4_ids AS (SELECT position_id FROM s19_position_data WHERE (UPPER(position_name) LIKE '%CORPORATE%' OR UPPER(position_name) LIKE '%PMU%') AND UPPER(position_name) NOT LIKE '%PLANNING SCHEDULING%'),
s19_row6_ids AS (SELECT position_id FROM s19_position_data WHERE UPPER(position_name) LIKE '%MM DIRECTORATE%' OR UPPER(position_name) LIKE '%DISPOSAL%' OR UPPER(position_name) LIKE '%MATERIAL MANAGEMENT%'),
s19_row7_ids AS (SELECT position_id FROM s19_position_data WHERE (UPPER(position_name) LIKE '%MANAGER MIS%' OR UPPER(position_name) LIKE '%MANAGER-MIS%' OR UPPER(position_name) LIKE '%IT DIRECTORATE%' OR UPPER(position_name) LIKE '%INFORMATION TECHNOLOGY%')),
s19_row8_ids AS (SELECT position_id FROM s19_position_data WHERE UPPER(position_name) LIKE '%INTERNAL AUDIT%'),
s19_row9_ids AS (SELECT position_id FROM s19_position_data WHERE UPPER(position_name) LIKE '%COMPANY SECRETARY%'),
s19_row10_ids AS (SELECT position_id FROM s19_position_data WHERE UPPER(position_name) LIKE '%REGULATORY AFFAIRS%' AND UPPER(position_name) NOT LIKE '%LEGAL%'),
s19_row11_ids AS (SELECT position_id FROM s19_position_data WHERE (UPPER(position_name) LIKE '%FORECASTING%')),
s19_row12_ids AS (SELECT position_id FROM s19_position_data WHERE UPPER(position_name) LIKE '%MANAGER (LEGAL%' OR (UPPER(position_name) LIKE '%LEGAL%' AND UPPER(position_name) LIKE '%CONTRACT%')),
s19_other_ids AS (SELECT DISTINCT position_id FROM (SELECT position_id FROM s19_row2_ids UNION ALL SELECT position_id FROM s19_row3_ids UNION ALL SELECT position_id FROM s19_row4_ids UNION ALL SELECT position_id FROM s19_row6_ids UNION ALL SELECT position_id FROM s19_row7_ids UNION ALL SELECT position_id FROM s19_row8_ids UNION ALL SELECT position_id FROM s19_row9_ids UNION ALL SELECT position_id FROM s19_row10_ids UNION ALL SELECT position_id FROM s19_row11_ids UNION ALL SELECT position_id FROM s19_row12_ids)),
s19_row1_ids AS (SELECT position_id FROM s19_position_data WHERE position_id NOT IN (SELECT position_id FROM s19_exclusion_list) AND position_id NOT IN (SELECT position_id FROM s19_other_ids)),

/* --- 3. FINAL ROW AGGREGATIONS --- */
s19_combined AS (
    SELECT '19' AS scale, 'SEs / Managers' AS designation, 
           NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working, 
           GREATEST(NVL(SUM(p.sanctioned), 0) - NVL(SUM(a.working), 0), 0) AS vacant, 
           GREATEST(NVL(SUM(a.working), 0) - NVL(SUM(p.sanctioned), 0), 0) AS surplus 
    FROM s19_position_data p LEFT JOIN s19_assignment_data a ON p.position_id = a.position_id 
    WHERE p.position_id IN (SELECT position_id FROM s19_row1_ids) 
      AND p.position_id NOT IN (SELECT position_id FROM s19_other_ids)
    UNION ALL
    SELECT '19' AS scale, 'Manager (HR)/(A&S)/(Confdl:)/(T&D)/(L&L)' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0), 
           GREATEST(NVL(SUM(p.sanctioned), 0) - NVL(SUM(a.working), 0), 0), 
           GREATEST(NVL(SUM(a.working), 0) - NVL(SUM(p.sanctioned), 0), 0) 
    FROM s19_position_data p LEFT JOIN s19_assignment_data a ON p.position_id = a.position_id 
    WHERE p.position_id IN (SELECT position_id FROM s19_row2_ids)
    UNION ALL
    SELECT '19' AS scale, 'Manager (Commercial)' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0), 
           GREATEST(NVL(SUM(p.sanctioned), 0) - NVL(SUM(a.working), 0), 0), 
           GREATEST(NVL(SUM(a.working), 0) - NVL(SUM(p.sanctioned), 0), 0) 
    FROM s19_position_data p LEFT JOIN s19_assignment_data a ON p.position_id = a.position_id 
    WHERE p.position_id IN (SELECT position_id FROM s19_row3_ids)
    UNION ALL
    SELECT '19' AS scale, 'Manager (Corporate Accounts) / (CP&C)/ PMU' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0), 
           GREATEST(NVL(SUM(p.sanctioned), 0) - NVL(SUM(a.working), 0), 0), 
           GREATEST(NVL(SUM(a.working), 0) - NVL(SUM(p.sanctioned), 0), 0) 
    FROM s19_position_data p LEFT JOIN s19_assignment_data a ON p.position_id = a.position_id 
    WHERE p.position_id IN (SELECT position_id FROM s19_row4_ids)
    UNION ALL
    SELECT '19' AS scale, 'Manager (MM) / (Disposal)' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0), 
           GREATEST(NVL(SUM(p.sanctioned), 0) - NVL(SUM(a.working), 0), 0), 
           GREATEST(NVL(SUM(a.working), 0) - NVL(SUM(p.sanctioned), 0), 0) 
    FROM s19_position_data p LEFT JOIN s19_assignment_data a ON p.position_id = a.position_id 
    WHERE p.position_id IN (SELECT position_id FROM s19_row6_ids)
    UNION ALL
    SELECT '19' AS scale, 'Managers (MIS) / IT (Operations) / B.Application' AS designation, 
          3 as sanctioned, NVL(SUM(a.working), 0), 
           GREATEST(NVL(SUM(p.sanctioned), 0) - NVL(SUM(a.working), 0), 0), 
           GREATEST(NVL(SUM(a.working), 0) - NVL(SUM(p.sanctioned), 0), 0) 
    FROM s19_position_data p LEFT JOIN s19_assignment_data a ON p.position_id = a.position_id 
    WHERE p.position_id IN (SELECT position_id FROM s19_row7_ids)
    UNION ALL
    SELECT '19' AS scale, 'Manager / Head of Internal Audit' AS designation, 
           1 AS sanctioned, NVL(SUM(a.working), 0), 
           GREATEST(NVL(SUM(p.sanctioned), 0) - NVL(SUM(a.working), 0), 0), 
           GREATEST(NVL(SUM(a.working), 0) - NVL(SUM(p.sanctioned), 0), 0) 
    FROM s19_position_data p LEFT JOIN s19_assignment_data a ON p.position_id = a.position_id 
    WHERE p.position_id IN (SELECT position_id FROM s19_row8_ids)
    UNION ALL
    SELECT '19' AS scale, 'Company Secretary' AS designation, 
           1 AS sanctioned, NVL(SUM(a.working), 0), 
           GREATEST(NVL(SUM(p.sanctioned), 0) - NVL(SUM(a.working), 0), 0), 
           GREATEST(NVL(SUM(a.working), 0) - NVL(SUM(p.sanctioned), 0), 0) 
    FROM s19_position_data p LEFT JOIN s19_assignment_data a ON p.position_id = a.position_id 
    WHERE p.position_id IN (SELECT position_id FROM s19_row9_ids)
    UNION ALL
    SELECT '19' AS scale, 'Manager (Contract Management and Regulatory Affairs)' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0), 
           GREATEST(NVL(SUM(p.sanctioned), 0) - NVL(SUM(a.working), 0), 0), 
           GREATEST(NVL(SUM(a.working), 0) - NVL(SUM(p.sanctioned), 0), 0) 
    FROM s19_position_data p LEFT JOIN s19_assignment_data a ON p.position_id = a.position_id 
    WHERE p.position_id IN (SELECT position_id FROM s19_row10_ids)
    UNION ALL
    SELECT '19' AS scale, 'Manager (Legal /Contract) MIRAD' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0), 
           GREATEST(NVL(SUM(p.sanctioned), 0) - NVL(SUM(a.working), 0), 0), 
           GREATEST(NVL(SUM(a.working), 0) - NVL(SUM(p.sanctioned), 0), 0) 
    FROM s19_position_data p LEFT JOIN s19_assignment_data a ON p.position_id = a.position_id 
    WHERE p.position_id IN (SELECT position_id FROM s19_row12_ids)
    UNION ALL
    SELECT '19' AS scale, 'Manager (Planning and Forecasting) MIRAD' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0), 
           GREATEST(NVL(SUM(p.sanctioned), 0) - NVL(SUM(a.working), 0), 0), 
           GREATEST(NVL(SUM(a.working), 0) - NVL(SUM(p.sanctioned), 0), 0) 
    FROM s19_position_data p LEFT JOIN s19_assignment_data a ON p.position_id = a.position_id 
    WHERE p.position_id IN (SELECT position_id FROM s19_row11_ids)
),

/* --- SCALE 20 BASE DATA --- */
s20_assignment_data AS (
    SELECT position_id, COUNT(*) AS working 
    FROM per_assignments_x 
    WHERE NVL(location_id, -1) <> 27625 
    GROUP BY position_id
),
s20_position_data AS (
    SELECT 
        pos.position_id, 
        pos.name AS position_name, 
        pos.max_persons AS sanctioned
    FROM hr.hr_all_positions_f pos
    JOIN per_jobs_vl job ON pos.job_id = job.job_id
    WHERE NVL(pos.location_id, -1) <> 27625
      AND (
        EXISTS (
            SELECT 1 FROM per_valid_grades_v vld 
            WHERE vld.job_id = job.job_id 
            AND REGEXP_LIKE(vld.name, '(^|[^0-9])20([^0-9]|$)')
        )
        OR UPPER(pos.name) LIKE '%DIRECTOR-FINANCE DIRECTORATE%'
      )
),
s20_exclusion_list AS (
    SELECT DISTINCT position_id FROM s20_position_data 
    WHERE UPPER(position_name) LIKE '%CE ON LEAVE%' 
       OR UPPER(position_name) LIKE '%INCHARGE-MIRAD%' 
       OR UPPER(position_name) LIKE '%CE ON LPR%'
),

/* --- 2. ROW DEFINITIONS --- */
s20_combined AS (
    SELECT '20' AS scale, 'Chief Executive Officer' AS designation, 
           NVL(SUM(p.sanctioned), 0) AS sanctioned, NVL(SUM(a.working), 0) AS working,
           GREATEST(NVL(SUM(p.sanctioned),0) - NVL(SUM(a.working),0), 0) AS vacant,
           GREATEST(NVL(SUM(a.working),0) - NVL(SUM(p.sanctioned),0), 0) AS surplus
    FROM s20_position_data p LEFT JOIN s20_assignment_data a ON p.position_id = a.position_id 
    WHERE UPPER(p.position_name) LIKE '%CHIEF EXECUTIVE OFFICER%' 
      AND p.position_id NOT IN (SELECT position_id FROM s20_exclusion_list)
    UNION ALL
    SELECT '20' AS scale, 'Chief Engineers' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0),
           GREATEST(NVL(SUM(p.sanctioned),0) - NVL(SUM(a.working),0), 0),
           GREATEST(NVL(SUM(a.working),0) - NVL(SUM(p.sanctioned),0), 0)
    FROM s20_position_data p LEFT JOIN s20_assignment_data a ON p.position_id = a.position_id 
    WHERE (UPPER(p.position_name) LIKE '%CHIEF ENGINEER%' OR UPPER(p.position_name) LIKE '%OPERATION OFFICER%') 
      AND p.position_id NOT IN (SELECT position_id FROM s20_exclusion_list)
    UNION ALL
    SELECT '20' AS scale, 'Director Finance' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0),
           GREATEST(NVL(SUM(p.sanctioned),0) - NVL(SUM(a.working),0), 0),
           GREATEST(NVL(SUM(a.working),0) - NVL(SUM(p.sanctioned),0), 0)
    FROM s20_position_data p LEFT JOIN s20_assignment_data a ON p.position_id = a.position_id 
    WHERE UPPER(p.position_name) LIKE '%DIRECTOR-FINANCE DIRECTORATE%' 
      AND p.position_id NOT IN (SELECT position_id FROM s20_exclusion_list)
    UNION ALL
    SELECT '20' AS scale, 'DG (HR)' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0),
           GREATEST(NVL(SUM(p.sanctioned),0) - NVL(SUM(a.working),0), 0),
           GREATEST(NVL(SUM(a.working),0) - NVL(SUM(p.sanctioned),0), 0)
    FROM s20_position_data p LEFT JOIN s20_assignment_data a ON p.position_id = a.position_id 
    WHERE UPPER(p.position_name) LIKE '%HR DIRECTORATE%' 
      AND p.position_id NOT IN (SELECT position_id FROM s20_exclusion_list)
    UNION ALL
    SELECT '20' AS scale, 'CITO' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0),
           GREATEST(NVL(SUM(p.sanctioned),0) - NVL(SUM(a.working),0), 0),
           GREATEST(NVL(SUM(a.working),0) - NVL(SUM(p.sanctioned),0), 0)
    FROM s20_position_data p LEFT JOIN s20_assignment_data a ON p.position_id = a.position_id 
    WHERE UPPER(p.position_name) LIKE '%CHIEF INFORMATION OFFICER%' 
      AND p.position_id NOT IN (SELECT position_id FROM s20_exclusion_list)
    UNION ALL
    SELECT '20' AS scale, 'Chief Law Officer' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0),
           GREATEST(NVL(SUM(p.sanctioned),0) - NVL(SUM(a.working),0), 0),
           GREATEST(NVL(SUM(a.working),0) - NVL(SUM(p.sanctioned),0), 0)
    FROM s20_position_data p LEFT JOIN s20_assignment_data a ON p.position_id = a.position_id 
    WHERE UPPER(p.position_name) LIKE '%CHIEF LAW OFFICER%' 
      AND p.position_id NOT IN (SELECT position_id FROM s20_exclusion_list)
    UNION ALL
    SELECT '20' AS scale, 'DG (MIRAD)' AS designation, 
           NVL(SUM(p.sanctioned), 0), NVL(SUM(a.working), 0),
           GREATEST(NVL(SUM(p.sanctioned),0) - NVL(SUM(a.working),0), 0),
           GREATEST(NVL(SUM(a.working),0) - NVL(SUM(p.sanctioned),0), 0)
    FROM s20_position_data p LEFT JOIN s20_assignment_data a ON p.position_id = a.position_id 
    WHERE UPPER(p.position_name) LIKE '%MIRAD%' 
      AND p.position_id NOT IN (SELECT position_id FROM s20_exclusion_list)
)

/* === FINAL COMBINED REPORT === */
SELECT scale, designation, sanctioned, working, vacant, surplus 
FROM s17_combined
UNION ALL
SELECT scale, designation, sanctioned, working, vacant, surplus 
FROM s18_combined
UNION ALL
SELECT scale, designation, sanctioned, working, vacant, surplus 
FROM s19_combined
UNION ALL
SELECT scale, designation, sanctioned, working, vacant, surplus 
FROM s20_combined
ORDER BY scale, designation

""",

"Job_Wise_Vacancy": """
WITH position_data AS (
    SELECT 
        pos.job_id,
        job.name AS Designation,
        SUM(pos.max_persons) AS sanctioned
    FROM 
        hr.hr_all_positions_f pos
    JOIN per_jobs job 
        ON job.job_id = pos.job_id
    WHERE 
        NVL(pos.location_id, -1) <> 27625
    GROUP BY 
        pos.job_id, job.name
),

assignment_data AS (
    SELECT 
        ass.job_id,

        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'REG' THEN 1 ELSE 0 END) AS regular,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'COT' THEN 1 ELSE 0 END) AS contract,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'CONSLSM' THEN 1 ELSE 0 END) AS lumpsum,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'XX_DEP' THEN 1 ELSE 0 END) AS deputation,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'DW' THEN 1 ELSE 0 END) AS daily_wages

    FROM 
        per_assignments_x ass
    WHERE 
        NVL(ass.location_id, -1) <> 27625
    GROUP BY 
        ass.job_id
)

SELECT 
    p.Designation,
    

    NVL(p.sanctioned,0) AS total_sanctioned,
    NVL(a.regular,0)    AS total_regular,
    NVL(a.contract,0)   AS total_contract,
    NVL(a.lumpsum,0)    AS total_lumpsum,
    NVL(a.deputation,0) AS total_deputation,
    NVL(a.daily_wages,0) AS total_daily_wages,

    NVL(a.regular, 0)
  + NVL(a.contract, 0)
  + NVL(a.lumpsum, 0)
  + NVL(a.deputation, 0)
  + NVL(a.daily_wages, 0) AS total_working,

    GREATEST(
        p.sanctioned -
        ( NVL(a.regular, 0)
        + NVL(a.contract, 0)
        + NVL(a.lumpsum, 0)
        + NVL(a.deputation, 0)
        + NVL(a.daily_wages, 0) ),
        0
    ) AS total_vacant

FROM 
    position_data p
LEFT JOIN 
    assignment_data a
ON 
    p.job_id = a.job_id
ORDER BY 
    p.Designation,p.job_id
""",

"Payroll": """
SELECT 
    petf.element_name AS earning_head,
    SUM(NVL(prrv.result_value, 0)) AS total
FROM
    pay_payroll_actions ppa
    JOIN pay_assignment_actions paa 
        ON paa.payroll_action_id = ppa.payroll_action_id
    JOIN pay_run_results prr 
        ON prr.assignment_action_id = paa.assignment_action_id
    JOIN pay_run_result_values prrv 
        ON prrv.run_result_id = prr.run_result_id
    JOIN pay_input_values_f pivf 
        ON pivf.input_value_id = prrv.input_value_id
    JOIN pay_element_types_f petf 
        ON prr.element_type_id = petf.element_type_id
    JOIN pay_element_classifications pec 
        ON petf.classification_id = pec.classification_id
WHERE
    pivf.name = 'Pay Value'
    AND petf.business_group_id = 81
    AND ppa.date_earned BETWEEN petf.effective_start_date AND petf.effective_end_date
    AND ppa.date_earned BETWEEN pivf.effective_start_date AND pivf.effective_end_date
    AND ppa.date_earned = TO_DATE(:p_payroll_date, 'YYYY-MM-DD')
    AND ppa.assignment_set_id = NVL(:p_assignment_set_id, ppa.assignment_set_id)
    AND pec.classification_name NOT LIKE '%Deduction%'     
    AND petf.element_name NOT IN (
        'TAX1', 'AB', 'Bonus', 'HQ_House_Accomodation', 
        'House Rent Deduction', 'House Rent', 'Int Allowance', 
        'Planning and Engineering Allowance','Adhoc Relief Allowance 2014','JOB_ALLOWANCE5','Washing and Livery Allowance','GSO Allowance','Miscellaneous ARREAR'
    )
GROUP BY 
    petf.element_name
ORDER BY 
    petf.element_name
""",

"Payroll_Deductions": """
SELECT 
    petf.element_name AS deduction_head,
    SUM(NVL(prrv.result_value, 0)) AS deduction_amount
FROM
    pay_payroll_actions ppa
    JOIN pay_assignment_actions paa ON paa.payroll_action_id = ppa.payroll_action_id
    JOIN pay_run_results prr ON prr.assignment_action_id = paa.assignment_action_id
    JOIN pay_run_result_values prrv ON prrv.run_result_id = prr.run_result_id
    JOIN pay_input_values_f pivf ON pivf.input_value_id = prrv.input_value_id
    JOIN pay_element_types_f petf ON prr.element_type_id = petf.element_type_id
    JOIN pay_element_classifications pec ON petf.classification_id = pec.classification_id
WHERE
    pivf.name = 'Pay Value'
    AND petf.business_group_id = 81
    AND ppa.date_earned = TO_DATE(:p_payroll_date, 'YYYY-MM-DD')
    /* This line is what "prompts" or filters by the ID */
    AND ppa.assignment_set_id = NVL(:p_assignment_set_id, ppa.assignment_set_id)
    AND pec.classification_name LIKE '%Deduction%'        
    AND petf.element_name NOT IN (
        'TAX1', 'AB', 'Bonus', 'HQ_House_Accomodation', 
        'House Rent Deduction', 'House Rent', 'Int Allowance', 
        'Planning and Engineering Allowance', 'TAX', 'Bonus Tax'
    )
GROUP BY 
    petf.element_name
ORDER BY 
    petf.element_name
""",

"3_Levels_of_Organization_Hierarchy_Vacancy": """
WITH org_hierarchy AS (
    /* PART 1: Existing Hierarchical Logic */
    SELECT
        child.organization_id    AS org_id,
        child.name               AS org_name,
        parent.name              AS parent_name,
        grandparent.name         AS grandparent_name
    FROM per_all_organization_units child
    LEFT JOIN per_org_structure_elements_v h1 
        ON child.organization_id = h1.organization_id_child
    LEFT JOIN per_all_organization_units parent 
        ON parent.organization_id = h1.organization_id_parent
    LEFT JOIN per_org_structure_elements_v h2 
        ON parent.organization_id = h2.organization_id_child
    LEFT JOIN per_all_organization_units grandparent 
        ON grandparent.organization_id = h2.organization_id_parent
    WHERE 1=1
      AND NVL(child.location_id, -1) NOT IN (27625)
      AND (parent.location_id IS NULL OR parent.location_id NOT IN (27625))
      AND (grandparent.location_id IS NULL OR grandparent.location_id NOT IN (27625))

    UNION ALL

    /* PART 2: Specific Location 25468 Logic */
    /* This captures offices at this location regardless of their hierarchy status */
    SELECT 
        org.organization_id        AS org_id,
        org.name                   AS org_name,
        'Location: 25468'          AS parent_name,      -- Custom label for Parent
        'Special Offices'          AS grandparent_name  -- Custom label for Top Level
    FROM per_all_organization_units org
    WHERE org.location_id = 25468
      AND NOT EXISTS (
          /* Prevents duplicates: if the office is already found in Part 1, skip it here */
          SELECT 1 FROM per_org_structure_elements_v 
          WHERE organization_id_child = org.organization_id
      )
),

position_data AS (
    SELECT 
        pos.organization_id,
        SUM(pos.max_persons) AS sanctioned
    FROM hr.hr_all_positions_f pos
    WHERE 1=1
      /* Ensure 25468 is allowed through even if it was caught in a general filter */
      AND (NVL(pos.location_id, -1) NOT IN (27625) OR pos.location_id = 25468)
      AND TRUNC(SYSDATE) BETWEEN pos.effective_start_date AND pos.effective_end_date
    GROUP BY pos.organization_id
),

assignment_data AS (
    SELECT 
        ass.organization_id,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'REG' THEN 1 ELSE 0 END) AS regular,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'COT' THEN 1 ELSE 0 END) AS contract,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'CONSLSM' THEN 1 ELSE 0 END) AS lumpsum,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'XX_DEP' THEN 1 ELSE 0 END) AS deputation,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'DW' THEN 1 ELSE 0 END) AS daily_wages
    FROM per_assignments_x ass
    WHERE 1=1
      AND (NVL(ass.location_id, -1) NOT IN (27625) OR ass.location_id = 25468)
      AND TRUNC(SYSDATE) BETWEEN ass.effective_start_date AND ass.effective_end_date
      AND ass.primary_flag = 'Y'
    GROUP BY ass.organization_id
)

SELECT
    oh.grandparent_name AS "Top Level Office",
    oh.parent_name      AS "Parent Office",
    oh.org_name          AS "Office Name",
    NVL(p.sanctioned, 0) AS "Total Sanctioned",
    ( NVL(a.regular,0) + NVL(a.contract,0) + NVL(a.lumpsum,0) + NVL(a.deputation,0) + NVL(a.daily_wages,0) ) AS "Total Working",
    GREATEST(
        NVL(p.sanctioned, 0) -
        ( NVL(a.regular,0) + NVL(a.contract,0) + NVL(a.lumpsum,0) + NVL(a.deputation,0) + NVL(a.daily_wages,0) ), 
        0
    ) AS "Total Vacant"
FROM org_hierarchy oh
INNER JOIN position_data p
    ON oh.org_id = p.organization_id
LEFT JOIN assignment_data a
    ON oh.org_id = a.organization_id
/* Note: IS NOT NULL filters removed to allow our custom labels from PART 2 to show */
ORDER BY 1, 2, 3
""",

"Retirement_Forecast": """
WITH retirement_data AS (
    SELECT
        paf.grade_id,
        EXTRACT(YEAR FROM (papf.date_of_birth + INTERVAL '60' YEAR)) AS retirement_year
    FROM per_all_people_f papf
    JOIN per_all_assignments_f paf
        ON papf.person_id = paf.person_id
    WHERE paf.assignment_type = 'E'
      AND paf.primary_flag = 'Y'
      AND TRUNC(SYSDATE) BETWEEN paf.effective_start_date AND paf.effective_end_date
      AND papf.current_employee_flag = 'Y'
      AND EXTRACT(YEAR FROM (papf.date_of_birth + INTERVAL '60' YEAR))
          BETWEEN EXTRACT(YEAR FROM SYSDATE)
              AND EXTRACT(YEAR FROM SYSDATE) + 4
)
SELECT
    g.name AS grade_name,
    SUM(CASE WHEN retirement_year = EXTRACT(YEAR FROM SYSDATE) THEN 1 ELSE 0 END) AS "YEAR 2026",
    SUM(CASE WHEN retirement_year = EXTRACT(YEAR FROM SYSDATE) + 1 THEN 1 ELSE 0 END) AS "YEAR 2027",
    SUM(CASE WHEN retirement_year = EXTRACT(YEAR FROM SYSDATE) + 2 THEN 1 ELSE 0 END) AS "YEAR 2028",
    SUM(CASE WHEN retirement_year = EXTRACT(YEAR FROM SYSDATE) + 3 THEN 1 ELSE 0 END) AS "YEAR 2029",
    SUM(CASE WHEN retirement_year = EXTRACT(YEAR FROM SYSDATE) + 4 THEN 1 ELSE 0 END) AS "YEAR 2030",
    COUNT(*) AS "Total"
FROM retirement_data r
LEFT JOIN per_grades g
    ON g.grade_id = r.grade_id
where g.name is not null
GROUP BY g.name
""",
"Payroll_Register":"""
Select DISTINCT
     papf.employee_number as employee_number
    --,papf.full_name as employee_name
    ,papf.first_name ||' '|| papf.middle_names ||' '||papf.last_name employee_name
    ,papf.national_identifier as cnic
    ,papf.attribute2 as gp_fund
    ,(select name from hr_all_organization_units where organization_id = paaf.organization_id ) as department
    ,(select name from per_positions where position_id = paaf.position_id ) as position
    ,(select name from per_jobs where job_id = paaf.job_id ) as designation
    ,(select name from per_grades    where grade_id    = paaf.grade_id ) as grade 
    ,nvl(sum(decode(petf.element_type_id,121,prrv.result_value)),0) basic_salary
    ,sum(decode(petf.element_type_id,138,prrv.result_value)) personal_pay
    /*,sum(decode(petf.element_type_id,123,prrv.result_value)) allowance_2010
    ,sum(decode(petf.element_type_id,124,prrv.result_value)) adhoc_relief_allowance_2013
    ,sum(decode(petf.element_type_id,125,prrv.result_value)) adhoc_relief_allowance_2014
    ,sum(decode(petf.element_type_id,126,prrv.result_value)) adhoc_relief_allowance_2015*/
    ,sum(decode(petf.element_type_id,460,prrv.result_value)) DRA21
    ,sum(decode(petf.element_type_id,478,prrv.result_value)) DRA22
    ,sum(decode(petf.element_type_id,345,prrv.result_value)) ARA22
    ,sum(decode(petf.element_type_id,458,prrv.result_value)) ARA23
    ,sum(decode(petf.element_type_id,456,prrv.result_value)) ARA24
    ----,sum(decode(petf.element_type_id,393,prrv.result_value)) house_rent_allowance
   ,sum(decode(petf.element_type_id,480,prrv.result_value)) house_rent_allowance
    ,sum(decode(petf.element_type_id,129,prrv.result_value)) cash_medical_allowance
    ,sum(decode(petf.element_type_id,146,prrv.result_value)) conveyance_allowance
    ,sum(decode(petf.element_type_id,131,prrv.result_value)) hard_area_allowance
    ,sum(decode(petf.element_type_id,141,prrv.result_value)) special_allowance
    ,sum(decode(petf.element_type_id,183,prrv.result_value)) danger_allowance
    ,sum(decode(petf.element_type_id,142,prrv.result_value)) wapda_special_relief_allowance
   -- ,sum(decode(petf.element_type_id,136,prrv.result_value)) livery_allowance
    ,sum(decode(petf.element_type_id,134,prrv.result_value)) integrated_allowance
    ,sum(decode(petf.element_type_id,201,prrv.result_value)) gli_allowance
    ,sum(decode(petf.element_type_id,391,prrv.result_value)) Misc_Arrear
   -- ,sum(decode(petf.element_type_id,182,prrv.result_value)) washing_allowance
    ,sum(decode(petf.element_type_id,387,prrv.result_value)) job_allowance
    ,sum(decode(petf.element_type_id,221,prrv.result_value)) motor_cycle_allowance
    ,sum(decode(petf.element_type_id,203,prrv.result_value)) special_pay
    ,sum(decode(petf.element_type_id,139,prrv.result_value)) qualification_pay
    ,sum(decode(petf.element_type_id,128,prrv.result_value)) entertainment_allowance
    ,sum(decode(petf.element_type_id,143,prrv.result_value)) special_security_allowance
    ,sum(decode(petf.element_type_id,130,prrv.result_value)) headquarter_allowance
    ,sum(decode(petf.element_type_id,140,prrv.result_value)) senior_post_allowance
    ,sum(decode(petf.element_type_id,132,prrv.result_value)) hill_area_allowance
    ,sum(decode(petf.element_type_id,137,prrv.result_value)) orderly_allowance
    ,sum(decode(petf.element_type_id,243,prrv.result_value)) gso_allowance
    ,sum(decode(petf.element_type_id,127,prrv.result_value)) appointment_allowance
    ,sum(decode(petf.element_type_id,135,prrv.result_value)) kit_allowance
    ,sum(decode(petf.element_type_id,241,prrv.result_value)) un_attracted_allowance
    ,sum(decode(petf.element_type_id,144,prrv.result_value)) technical_allowance
    ,sum(decode(petf.element_type_id,145,prrv.result_value)) transport_subsidy
    ,sum(decode(petf.classification_id,124,nvl(prrv.result_value,0))) gross_pay
    -- start deduction
    ,sum(decode(petf.element_type_id,151,prrv.result_value)) union_fund
    ,sum(decode(petf.element_type_id,193,prrv.result_value)) income_tax
    ,sum(decode(petf.element_type_id,152,prrv.result_value)) wapda_welfare_fund
    ,sum(decode(petf.element_type_id,181,prrv.result_value)) gli_deduction
    ,sum(decode(petf.element_type_id,150,prrv.result_value)) medical_benevolent_fund
    ,sum(decode(petf.element_type_id,202,prrv.result_value)) house_rent_deduction
    ,sum(decode(petf.element_type_id,147,prrv.result_value)) bus_charges
    ,sum(decode(petf.element_type_id,395,prrv.result_value)) Misc_Recovery
    ,sum(decode(petf.element_type_id,519,prrv.result_value)) GP_Fund_Advance_I
    ,sum(decode(petf.element_type_id,520,prrv.result_value)) GP_Fund_Advance_II
    ,sum(decode(petf.element_type_id,392,prrv.result_value)) govt_provident_fund
    -- total_amounts
    ,nvl(sum(decode(petf.classification_id,127,nvl(prrv.result_value,0))),0) total_deduction
    ,nvl(sum(decode(petf.classification_id,124,nvl(prrv.result_value,0))),0) - nvl(sum(decode(petf.classification_id,127,nvl(prrv.result_value,0))),0) net_salary
    ,sum(decode(petf.element_type_id,189,prrv.result_value)) daily_wages_salary
from
    per_all_people_f                papf
    ,per_all_assignments_f           paaf
    ,per_periods_of_service      ppos    
    ,hr_all_organization_units       hou
    ,pay_cost_allocation_keyflex pca
    ,per_time_periods            ptp
    ,pay_payroll_actions         ppa
    ,pay_assignment_actions      paa
    ,pay_element_classifications pec
    ,pay_element_types_f         petf
    ,pay_input_values_f          pivf
    ,pay_run_results            prr
    ,pay_run_result_values       prrv
    ,pay_people_groups ppg
    ,hr_locations_all hla
    ,(select sno, assignment_id,org_payment_method_id,currency1 from
    (
    select rownum sno, ppm.assignment_id,ppm.org_payment_method_id,opm.currency_code currency1
    ,opm.org_payment_method_name
    from
    pay_personal_payment_methods_f ppm,
    pay_org_payment_methods_f      opm
    where
    1=1
    and ppm.org_payment_method_id = opm.org_payment_method_id
    and opm.business_group_id=ppm.business_group_id
    and sysdate between ppm.effective_start_date and ppm.effective_end_date
    and sysdate between opm.effective_start_date and opm.effective_end_date
    ---- and ppm.assignment_id =644
    and opm.business_group_id = 81
    )
    where
    sno=1
    ) pcur1
    ,(select sno, assignment_id,org_payment_method_id,currency2 from
    (
    select rownum sno, ppm.assignment_id,ppm.org_payment_method_id,opm.currency_code currency2
    ,opm.org_payment_method_name
    from
    pay_personal_payment_methods_f ppm,
    pay_org_payment_methods_f      opm
    where
    ppm.org_payment_method_id = opm.org_payment_method_id
    and opm.business_group_id=ppm.business_group_id
    and sysdate between ppm.effective_start_date and ppm.effective_end_date
    and sysdate between opm.effective_start_date and opm.effective_end_date
    ---- and ppm.assignment_id =644
    and opm.business_group_id = 81
    )
    where
    sno = 2
    ) pcur2
where 
    papf.business_group_id = 81 -- fnd_profile.value('PER_BUSINESS_GROUP_ID') 
    and papf.person_id                 = paaf.person_id
    and paaf.period_of_service_id      = ppos.period_of_service_id
    and paa.assignment_id              = paaf.assignment_id
    and paaf.organization_id           = hou.organization_id
    and hou.cost_allocation_keyflex_id = pca.cost_allocation_keyflex_id(+)
    and ppa.payroll_id                 = paaf.payroll_id
    and ppa.time_period_id             = ptp.time_period_id
    and ppa.action_type                in  ('R','Q')  --- R=run Q=QuickRun
    and paa.payroll_action_id          = ppa.payroll_action_id
    and paaf.payroll_id                = ptp.payroll_id  
    and petf.classification_id         = pec.classification_id
    and prr.assignment_action_id       = paa.assignment_action_id
    and petf.element_type_id           = prr.element_type_id 
    and petf.element_type_id           = pivf.element_type_id  
    and pivf.input_value_id            = prrv.input_value_id
    and prr.run_result_id              = prrv.run_result_id
    and ppa.date_earned between ptp.start_date and ptp.end_date
    and ppa.date_earned between paaf.effective_start_date and paaf.effective_end_date
    and ppa.date_earned between papf.effective_start_date and papf.effective_end_date
    and pivf.name in ('Pay Value')
    and paaf.people_group_id = ppg.people_group_id
    and paaf.assignment_id =pcur1.assignment_id (+)
    and paaf.assignment_id =pcur2.assignment_id (+)
    and paaf.location_id = hla.location_id
    --parameter
    and papf.employee_number = nvl(:p_emp_no,papf.employee_number)
    and ppa. assignment_set_id = nvl(:p_assignment_set_id,ppa. assignment_set_id)
    and paaf.job_id = nvl(:p_job_id, paaf.job_id)
    and paaf.grade_id = nvl(:p_grade_id, paaf.grade_id)
    and paaf.organization_id = nvl(:p_org_id ,paaf.organization_id)
and TRUNC(ppa.date_earned) = TO_DATE(:p_payroll_date, 'YYYY-MM-DD')
    and hla.town_or_city = nvl(:p_city,hla.town_or_city)
    -- and &p_con
group by 
    papf.person_id,
    paaf.assignment_id,
    ppa.date_earned,
    ptp.end_date,
    paaf.job_id,
    paaf.position_id,
    paaf.grade_id,
    papf.employee_number ,
    ---papf.full_name ,
    papf.first_name,
    papf.middle_names,
    papf.last_name,
    paaf.organization_id,
    papf.national_identifier,
    papf.attribute2
""",

"Sub_Division_Wise_Vacancy": """
WITH position_data AS (
    SELECT 
        pos.organization_id,
        org.name AS office_name,
        SUM(pos.max_persons) AS sanctioned
    FROM hr.hr_all_positions_f pos
    INNER JOIN per_all_organization_units org 
        ON org.organization_id = pos.organization_id
    WHERE 1=1
      /* FILTER 1: Scrub the Position Location */
      AND NVL(pos.location_id, -1) NOT IN (27625)
      /* FILTER 2: Scrub the Organization Location (The leak source) */
      AND NVL(org.location_id, -1) NOT IN (27625)
      AND TRUNC(SYSDATE) BETWEEN pos.effective_start_date AND pos.effective_end_date
    GROUP BY pos.organization_id, org.name
),

assignment_data AS (
    SELECT 
        ass.organization_id,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'REG' THEN 1 ELSE 0 END) AS regular,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'COT' THEN 1 ELSE 0 END) AS contract,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'CONSLSM' THEN 1 ELSE 0 END) AS lumpsum,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'XX_DEP' THEN 1 ELSE 0 END) AS deputation,
        SUM(CASE WHEN UPPER(TRIM(ass.employment_category)) = 'DW' THEN 1 ELSE 0 END) AS daily_wages
    FROM per_assignments_x ass
    WHERE 1=1
      /* FILTER 3: Scrub the Assignment Location */
      AND NVL(ass.location_id, -1) NOT IN (27625)
      AND TRUNC(SYSDATE) BETWEEN ass.effective_start_date AND ass.effective_end_date
      AND ass.primary_flag = 'Y'
    GROUP BY ass.organization_id
)

SELECT 
    p.office_name AS "Office Name",
    NVL(p.sanctioned, 0) AS "Total Sanctioned",
    ( NVL(a.regular, 0)
    + NVL(a.contract, 0)
    + NVL(a.lumpsum, 0)
    + NVL(a.deputation, 0)
    + NVL(a.daily_wages, 0) ) AS "Total Working",
    GREATEST(
        NVL(p.sanctioned, 0) -
        ( NVL(a.regular, 0)
        + NVL(a.contract, 0)
        + NVL(a.lumpsum, 0)
        + NVL(a.deputation, 0)
        + NVL(a.daily_wages, 0) ), 0
    ) AS "Total Vacant"
FROM position_data p
/* Use LEFT JOIN to keep offices that are sanctioned but have 0 staff */
LEFT JOIN assignment_data a
    ON p.organization_id = a.organization_id
ORDER BY p.office_name
""",
"Bulk_Salary_Slips": """
SELECT DISTINCT
    papf.employee_number AS employee_number,
    papf.first_name ||' '|| papf.middle_names ||' '||papf.last_name AS employee_name,
    papf.national_identifier AS cnic,
    papf.attribute2 AS gp_fund,
    (SELECT name FROM hr_all_organization_units WHERE organization_id = paaf.organization_id) AS department,
    (SELECT name FROM per_positions WHERE position_id = paaf.position_id) AS position,
    (SELECT name FROM per_jobs WHERE job_id = paaf.job_id) AS designation,
    (SELECT name FROM per_grades WHERE grade_id = paaf.grade_id) AS grade,
    NVL(SUM(DECODE(petf.element_type_id, 121, prrv.result_value)), 0) AS basic_salary,
    SUM(DECODE(petf.element_type_id, 138, prrv.result_value)) AS personal_pay,
    SUM(DECODE(petf.element_type_id, 460, prrv.result_value)) AS DRA21,
    SUM(DECODE(petf.element_type_id, 478, prrv.result_value)) AS DRA22,
    SUM(DECODE(petf.element_type_id, 345, prrv.result_value)) AS ARA22,
    SUM(DECODE(petf.element_type_id, 458, prrv.result_value)) AS ARA23,
    SUM(DECODE(petf.element_type_id, 456, prrv.result_value)) AS ARA24,
    SUM(DECODE(petf.element_type_id, 458, prrv.result_value)) AS ARA25,
    SUM(DECODE(petf.element_type_id, 456, prrv.result_value)) AS DRA25,
    SUM(DECODE(petf.element_type_id, 456, prrv.result_value)) AS miscellaneous_allowance,
    SUM(DECODE(petf.element_type_id, 480, prrv.result_value)) AS house_rent_allowance,
    SUM(DECODE(petf.element_type_id, 129, prrv.result_value)) AS cash_medical_allowance,
    SUM(DECODE(petf.element_type_id, 146, prrv.result_value)) AS conveyance_allowance,
    SUM(DECODE(petf.element_type_id, 131, prrv.result_value)) AS hard_area_allowance,
    SUM(DECODE(petf.element_type_id, 141, prrv.result_value)) AS special_allowance,
    SUM(DECODE(petf.element_type_id, 183, prrv.result_value)) AS danger_allowance,
    SUM(DECODE(petf.element_type_id, 142, prrv.result_value)) AS wapda_special_relief_allowance,
    SUM(DECODE(petf.element_type_id, 134, prrv.result_value)) AS integrated_allowance,
    SUM(DECODE(petf.element_type_id, 201, prrv.result_value)) AS gli_allowance,
    SUM(DECODE(petf.element_type_id, 391, prrv.result_value)) AS Misc_Arrear,
    SUM(DECODE(petf.element_type_id, 387, prrv.result_value)) AS job_allowance,
    SUM(DECODE(petf.element_type_id, 221, prrv.result_value)) AS motor_cycle_allowance,
    SUM(DECODE(petf.element_type_id, 203, prrv.result_value)) AS special_pay,
    SUM(DECODE(petf.element_type_id, 139, prrv.result_value)) AS qualification_pay,
    SUM(DECODE(petf.element_type_id, 128, prrv.result_value)) AS entertainment_allowance,
    SUM(DECODE(petf.element_type_id, 143, prrv.result_value)) AS special_security_allowance,
    SUM(DECODE(petf.element_type_id, 130, prrv.result_value)) AS headquarter_allowance,
    SUM(DECODE(petf.element_type_id, 140, prrv.result_value)) AS senior_post_allowance,
    SUM(DECODE(petf.element_type_id, 132, prrv.result_value)) AS hill_area_allowance,
    SUM(DECODE(petf.element_type_id, 137, prrv.result_value)) AS orderly_allowance,
    SUM(DECODE(petf.element_type_id, 243, prrv.result_value)) AS gso_allowance,
    SUM(DECODE(petf.element_type_id, 127, prrv.result_value)) AS appointment_allowance,
    SUM(DECODE(petf.element_type_id, 135, prrv.result_value)) AS kit_allowance,
    SUM(DECODE(petf.element_type_id, 241, prrv.result_value)) AS un_attracted_allowance,
    SUM(DECODE(petf.element_type_id, 144, prrv.result_value)) AS technical_allowance,
    SUM(DECODE(petf.element_type_id, 145, prrv.result_value)) AS transport_subsidy,
    SUM(DECODE(petf.classification_id, 124, NVL(prrv.result_value, 0))) AS gross_pay,
    -- Deductions
    SUM(DECODE(petf.element_type_id, 151, prrv.result_value)) AS union_fund,
    SUM(DECODE(petf.element_type_id, 193, prrv.result_value)) AS income_tax,
    SUM(DECODE(petf.element_type_id, 152, prrv.result_value)) AS wapda_welfare_fund,
    SUM(DECODE(petf.element_type_id, 181, prrv.result_value)) AS gli_deduction,
    SUM(DECODE(petf.element_type_id, 150, prrv.result_value)) AS medical_benevolent_fund,
    SUM(DECODE(petf.element_type_id, 202, prrv.result_value)) AS house_rent_deduction,
    SUM(DECODE(petf.element_type_id, 147, prrv.result_value)) AS bus_charges,
    SUM(DECODE(petf.element_type_id, 395, prrv.result_value)) AS Misc_Recovery,
    SUM(DECODE(petf.element_type_id, 519, prrv.result_value)) AS GP_Fund_Advance_I,
    SUM(DECODE(petf.element_type_id, 520, prrv.result_value)) AS GP_Fund_Advance_II,
    SUM(DECODE(petf.element_type_id, 392, prrv.result_value)) AS govt_provident_fund,
    NVL(SUM(DECODE(petf.classification_id, 127, NVL(prrv.result_value, 0))), 0) AS total_deduction,
    NVL(SUM(DECODE(petf.classification_id, 124, NVL(prrv.result_value, 0))), 0) -
    NVL(SUM(DECODE(petf.classification_id, 127, NVL(prrv.result_value, 0))), 0) AS net_salary,
    SUM(DECODE(petf.element_type_id, 189, prrv.result_value)) AS daily_wages_salary
FROM
    per_all_people_f papf,
    per_all_assignments_f paaf,
    per_periods_of_service ppos,
    hr_all_organization_units hou,
    pay_cost_allocation_keyflex pca,
    per_time_periods ptp,
    pay_payroll_actions ppa,
    pay_assignment_actions paa,
    pay_element_classifications pec,
    pay_element_types_f petf,
    pay_input_values_f pivf,
    pay_run_results prr,
    pay_run_result_values prrv,
    pay_people_groups ppg,
    hr_locations_all hla,
    (SELECT sno, assignment_id, org_payment_method_id, currency1 FROM (
        SELECT rownum sno, ppm.assignment_id, ppm.org_payment_method_id, opm.currency_code currency1
        FROM pay_personal_payment_methods_f ppm, pay_org_payment_methods_f opm
        WHERE ppm.org_payment_method_id = opm.org_payment_method_id
        AND opm.business_group_id = ppm.business_group_id
        AND SYSDATE BETWEEN ppm.effective_start_date AND ppm.effective_end_date
        AND SYSDATE BETWEEN opm.effective_start_date AND opm.effective_end_date
        AND opm.business_group_id = 81
    ) WHERE sno = 1) pcur1,
    (SELECT sno, assignment_id, org_payment_method_id, currency2 FROM (
        SELECT rownum sno, ppm.assignment_id, ppm.org_payment_method_id, opm.currency_code currency2
        FROM pay_personal_payment_methods_f ppm, pay_org_payment_methods_f opm
        WHERE ppm.org_payment_method_id = opm.org_payment_method_id
        AND opm.business_group_id = ppm.business_group_id
        AND SYSDATE BETWEEN ppm.effective_start_date AND ppm.effective_end_date
        AND SYSDATE BETWEEN opm.effective_start_date AND opm.effective_end_date
        AND opm.business_group_id = 81
    ) WHERE sno = 2) pcur2
WHERE
    papf.business_group_id = 81
    AND papf.person_id = paaf.person_id
    AND paaf.period_of_service_id = ppos.period_of_service_id
    AND paa.assignment_id = paaf.assignment_id
    AND paaf.organization_id = hou.organization_id
    AND hou.cost_allocation_keyflex_id = pca.cost_allocation_keyflex_id(+)
    AND ppa.payroll_id = paaf.payroll_id
    AND ppa.time_period_id = ptp.time_period_id
    AND ppa.action_type IN ('R', 'Q')
    AND paa.payroll_action_id = ppa.payroll_action_id
    AND paaf.payroll_id = ptp.payroll_id
    AND petf.classification_id = pec.classification_id
    AND prr.assignment_action_id = paa.assignment_action_id
    AND petf.element_type_id = prr.element_type_id
    AND petf.element_type_id = pivf.element_type_id
    AND pivf.input_value_id = prrv.input_value_id
    AND prr.run_result_id = prrv.run_result_id
    AND ppa.date_earned BETWEEN ptp.start_date AND ptp.end_date
    AND ppa.date_earned BETWEEN paaf.effective_start_date AND paaf.effective_end_date
    AND ppa.date_earned BETWEEN papf.effective_start_date AND papf.effective_end_date
    AND pivf.name = 'Pay Value'
    AND paaf.people_group_id = ppg.people_group_id
    AND paaf.assignment_id = pcur1.assignment_id(+)
    AND paaf.assignment_id = pcur2.assignment_id(+)
    AND paaf.location_id = hla.location_id
    -- Parameter filters (all optional)
    AND papf.employee_number = NVL(:p_emp_no, papf.employee_number)
    AND ppa.assignment_set_id = NVL(:p_assignment_set_id, ppa.assignment_set_id)
    AND hla.town_or_city = NVL(:p_city, hla.town_or_city)
    AND TRUNC(ppa.date_earned) = TO_DATE(:p_payroll_date, 'DD-MON-YYYY')
GROUP BY
    papf.person_id,
    paaf.assignment_id,
    ppa.date_earned,
    ptp.end_date,
    paaf.job_id,
    paaf.position_id,
    paaf.grade_id,
    papf.employee_number,
    papf.first_name,
    papf.middle_names,
    papf.last_name,
    paaf.organization_id,
    papf.national_identifier,
    papf.attribute2
""",

"Salary_Slip":"""

Select DISTINCT
     papf.employee_number as employee_number
    --,papf.full_name as employee_name
    ,papf.first_name ||' '|| papf.middle_names ||' '||papf.last_name employee_name
    ,papf.national_identifier as cnic
    ,papf.attribute2 as gp_fund
    ,(select name from hr_all_organization_units where organization_id = paaf.organization_id ) as department
    ,(select name from per_positions where position_id = paaf.position_id ) as position
    ,(select name from per_jobs where job_id = paaf.job_id ) as designation
    ,(select name from per_grades    where grade_id    = paaf.grade_id ) as grade 
    ,nvl(sum(decode(petf.element_type_id,121,prrv.result_value)),0) basic_salary
    ,sum(decode(petf.element_type_id,138,prrv.result_value)) personal_pay
    /*,sum(decode(petf.element_type_id,123,prrv.result_value)) allowance_2010
    ,sum(decode(petf.element_type_id,124,prrv.result_value)) adhoc_relief_allowance_2013
    ,sum(decode(petf.element_type_id,125,prrv.result_value)) adhoc_relief_allowance_2014
    ,sum(decode(petf.element_type_id,126,prrv.result_value)) adhoc_relief_allowance_2015*/
    ,sum(decode(petf.element_type_id,460,prrv.result_value)) DRA21
    ,sum(decode(petf.element_type_id,478,prrv.result_value)) DRA22
    ,sum(decode(petf.element_type_id,345,prrv.result_value)) ARA22
    ,sum(decode(petf.element_type_id,458,prrv.result_value)) ARA23
    ,sum(decode(petf.element_type_id,456,prrv.result_value)) ARA24
 ,sum(decode(petf.element_type_id,458,prrv.result_value)) ARA25
    ,sum(decode(petf.element_type_id,456,prrv.result_value)) DRA25
,sum(decode(petf.element_type_id,456,prrv.result_value)) miscellaneous_allowance
    ----,sum(decode(petf.element_type_id,393,prrv.result_value)) house_rent_allowance
   ,sum(decode(petf.element_type_id,480,prrv.result_value)) house_rent_allowance
    ,sum(decode(petf.element_type_id,129,prrv.result_value)) cash_medical_allowance
    ,sum(decode(petf.element_type_id,146,prrv.result_value)) conveyance_allowance
    ,sum(decode(petf.element_type_id,131,prrv.result_value)) hard_area_allowance
    ,sum(decode(petf.element_type_id,141,prrv.result_value)) special_allowance
    ,sum(decode(petf.element_type_id,183,prrv.result_value)) danger_allowance
    ,sum(decode(petf.element_type_id,142,prrv.result_value)) wapda_special_relief_allowance
   -- ,sum(decode(petf.element_type_id,136,prrv.result_value)) livery_allowance
    ,sum(decode(petf.element_type_id,134,prrv.result_value)) integrated_allowance
    ,sum(decode(petf.element_type_id,201,prrv.result_value)) gli_allowance
    ,sum(decode(petf.element_type_id,391,prrv.result_value)) Misc_Arrear
   -- ,sum(decode(petf.element_type_id,182,prrv.result_value)) washing_allowance
    ,sum(decode(petf.element_type_id,387,prrv.result_value)) job_allowance
    ,sum(decode(petf.element_type_id,221,prrv.result_value)) motor_cycle_allowance
    ,sum(decode(petf.element_type_id,203,prrv.result_value)) special_pay
    ,sum(decode(petf.element_type_id,139,prrv.result_value)) qualification_pay
    ,sum(decode(petf.element_type_id,128,prrv.result_value)) entertainment_allowance
    ,sum(decode(petf.element_type_id,143,prrv.result_value)) special_security_allowance
    ,sum(decode(petf.element_type_id,130,prrv.result_value)) headquarter_allowance
    ,sum(decode(petf.element_type_id,140,prrv.result_value)) senior_post_allowance
    ,sum(decode(petf.element_type_id,132,prrv.result_value)) hill_area_allowance
    ,sum(decode(petf.element_type_id,137,prrv.result_value)) orderly_allowance
    ,sum(decode(petf.element_type_id,243,prrv.result_value)) gso_allowance
    ,sum(decode(petf.element_type_id,127,prrv.result_value)) appointment_allowance
    ,sum(decode(petf.element_type_id,135,prrv.result_value)) kit_allowance
    ,sum(decode(petf.element_type_id,241,prrv.result_value)) un_attracted_allowance
    ,sum(decode(petf.element_type_id,144,prrv.result_value)) technical_allowance
    ,sum(decode(petf.element_type_id,145,prrv.result_value)) transport_subsidy
    ,sum(decode(petf.classification_id,124,nvl(prrv.result_value,0))) gross_pay
    -- start deduction
    ,sum(decode(petf.element_type_id,151,prrv.result_value)) union_fund
    ,sum(decode(petf.element_type_id,193,prrv.result_value)) income_tax
    ,sum(decode(petf.element_type_id,152,prrv.result_value)) wapda_welfare_fund
    ,sum(decode(petf.element_type_id,181,prrv.result_value)) gli_deduction
    ,sum(decode(petf.element_type_id,150,prrv.result_value)) medical_benevolent_fund
    ,sum(decode(petf.element_type_id,202,prrv.result_value)) house_rent_deduction
    ,sum(decode(petf.element_type_id,147,prrv.result_value)) bus_charges
    ,sum(decode(petf.element_type_id,395,prrv.result_value)) Misc_Recovery
    ,sum(decode(petf.element_type_id,519,prrv.result_value)) GP_Fund_Advance_I
    ,sum(decode(petf.element_type_id,520,prrv.result_value)) GP_Fund_Advance_II
    ,sum(decode(petf.element_type_id,392,prrv.result_value)) govt_provident_fund
    -- total_amounts
    ,nvl(sum(decode(petf.classification_id,127,nvl(prrv.result_value,0))),0) total_deduction
    ,nvl(sum(decode(petf.classification_id,124,nvl(prrv.result_value,0))),0) - nvl(sum(decode(petf.classification_id,127,nvl(prrv.result_value,0))),0) net_salary
    ,sum(decode(petf.element_type_id,189,prrv.result_value)) daily_wages_salary
from
    per_all_people_f                papf
    ,per_all_assignments_f           paaf
    ,per_periods_of_service      ppos    
    ,hr_all_organization_units       hou
    ,pay_cost_allocation_keyflex pca
    ,per_time_periods            ptp
    ,pay_payroll_actions         ppa
    ,pay_assignment_actions      paa
    ,pay_element_classifications pec
    ,pay_element_types_f         petf
    ,pay_input_values_f          pivf
    ,pay_run_results            prr
    ,pay_run_result_values       prrv
    ,pay_people_groups ppg
    ,hr_locations_all hla
    ,(select sno, assignment_id,org_payment_method_id,currency1 from
    (
    select rownum sno, ppm.assignment_id,ppm.org_payment_method_id,opm.currency_code currency1
    ,opm.org_payment_method_name
    from
    pay_personal_payment_methods_f ppm,
    pay_org_payment_methods_f      opm
    where
    1=1
    and ppm.org_payment_method_id = opm.org_payment_method_id
    and opm.business_group_id=ppm.business_group_id
    and sysdate between ppm.effective_start_date and ppm.effective_end_date
    and sysdate between opm.effective_start_date and opm.effective_end_date
    ---- and ppm.assignment_id =644
    and opm.business_group_id = 81
    )
    where
    sno=1
    ) pcur1
    ,(select sno, assignment_id,org_payment_method_id,currency2 from
    (
    select rownum sno, ppm.assignment_id,ppm.org_payment_method_id,opm.currency_code currency2
    ,opm.org_payment_method_name
    from
    pay_personal_payment_methods_f ppm,
    pay_org_payment_methods_f      opm
    where
    ppm.org_payment_method_id = opm.org_payment_method_id
    and opm.business_group_id=ppm.business_group_id
    and sysdate between ppm.effective_start_date and ppm.effective_end_date
    and sysdate between opm.effective_start_date and opm.effective_end_date
    ---- and ppm.assignment_id =644
    and opm.business_group_id = 81
    )
    where
    sno = 2
    ) pcur2
where 
    papf.business_group_id = 81 -- fnd_profile.value('PER_BUSINESS_GROUP_ID') 
    and papf.person_id                 = paaf.person_id
    and paaf.period_of_service_id      = ppos.period_of_service_id
    and paa.assignment_id              = paaf.assignment_id
    and paaf.organization_id           = hou.organization_id
    and hou.cost_allocation_keyflex_id = pca.cost_allocation_keyflex_id(+)
    and ppa.payroll_id                 = paaf.payroll_id
    and ppa.time_period_id             = ptp.time_period_id
    and ppa.action_type                in  ('R','Q')  --- R=run Q=QuickRun
    and paa.payroll_action_id          = ppa.payroll_action_id
    and paaf.payroll_id                = ptp.payroll_id  
    and petf.classification_id         = pec.classification_id
    and prr.assignment_action_id       = paa.assignment_action_id
    and petf.element_type_id           = prr.element_type_id 
    and petf.element_type_id           = pivf.element_type_id  
    and pivf.input_value_id            = prrv.input_value_id
    and prr.run_result_id              = prrv.run_result_id
    and ppa.date_earned between ptp.start_date and ptp.end_date
    and ppa.date_earned between paaf.effective_start_date and paaf.effective_end_date
    and ppa.date_earned between papf.effective_start_date and papf.effective_end_date
    and pivf.name in ('Pay Value')
    and paaf.people_group_id = ppg.people_group_id
    and paaf.assignment_id =pcur1.assignment_id (+)
    and paaf.assignment_id =pcur2.assignment_id (+)
    and paaf.location_id = hla.location_id
    --parameter
    and papf.employee_number = nvl(:p_emp_no,papf.employee_number)
and TRUNC(ppa.date_earned) = TO_DATE(:p_payroll_date, 'YYYY-MM-DD')
    and hla.town_or_city = nvl(:p_city,hla.town_or_city)
    -- and &p_con
group by 
    papf.person_id,
    paaf.assignment_id,
    ppa.date_earned,
    ptp.end_date,
    paaf.job_id,
    paaf.position_id,
    paaf.grade_id,
    papf.employee_number ,
    ---papf.full_name ,
    papf.first_name,
    papf.middle_names,
    papf.last_name,
    paaf.organization_id,
    papf.national_identifier,
    papf.attribute2
"""
}
def run_query(sql, params=None):
    cursor = connection.cursor()
    try:
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor]
    finally:
        cursor.close()

@app.route('/api/Salary_Slip')
def get_salary_slip():
    emp_no = request.args.get('emp_no')
    p_date = request.args.get('date') # Expected format YYYY-MM-DD from the browser

    # ONLY include the variables that actually appear in your SQL above
    params = {
        "p_emp_no": emp_no,
        "p_payroll_date": p_date,
        "p_city": None  # Included because :p_city is in your WHERE clause
    }

    try:
        # run_query helper
        data = run_query(queries["Salary_Slip"], params)
        return jsonify(data)
    except Exception as e:
        print(f"SQL Error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/<query_name>")
def get_data(query_name):
    # Standardize the key
    clean_key = query_name.replace(" ", "_")
    sql = queries.get(clean_key)
    	
    if not sql:
        return jsonify({"error": f"Query {clean_key} not found"}), 404

    params = None
    
    # --- TARGETED FIX FOR PAYROLL REGISTER ---
    if clean_key == "Payroll_Register":
        # Capture all 7 potential parameters from the URL
        params = {
            "p_payroll_date": request.args.get("p_payroll_date") or "2026-03-01",
            "p_emp_no": request.args.get("p_emp_no") or None,
            "p_assignment_set_id": request.args.get("p_assignment_set_id") or None,
            "p_job_id": request.args.get("p_job_id") or None,
            "p_grade_id": request.args.get("p_grade_id") or None,
            "p_org_id": request.args.get("p_org_id") or None,
            "p_city": request.args.get("p_city") or None
        }
    
    # --- EXISTING LOGIC FOR OTHER PAYROLL REPORTS ---
    elif "Payroll" in clean_key:
        p_date = request.args.get("date") or "2026-03-25"
        p_set_id = request.args.get("set_id")
        params = {
            "p_payroll_date": p_date,
            "p_assignment_set_id": p_set_id if (p_set_id and p_set_id.strip() != "") else None
        }

    try:
        # Now params contains all 7 keys for the Register, satisfying Oracle
        data = run_query(sql, params)
        return jsonify(data)
    except Exception as e:
        print(f"Error executing {clean_key}: {e}")
        return jsonify({"error": str(e)}), 500

# Remove the individual @app.route('/api/Payroll_Earnings') 
# and @app.route('/api/Payroll_Deductions') blocks entirely.
# They are now handled by the unified /api/<query_name> route above.


@app.route('/api/Payroll_Deductions')
def get_payroll_deductions():
    payroll_date = request.args.get('date')
    assignment_set_id = request.args.get('set_id')

    if not payroll_date or payroll_date == "undefined":
        return jsonify([])

    sql = """
    SELECT 
        petf.element_name AS deduction_head,
        SUM(NVL(prrv.result_value, 0)) AS total
    FROM pay_payroll_actions ppa
    JOIN pay_assignment_actions paa ON paa.payroll_action_id = ppa.payroll_action_id
    JOIN pay_run_results prr ON prr.assignment_action_id = paa.assignment_action_id
    JOIN pay_run_result_values prrv ON prrv.run_result_id = prr.run_result_id
    JOIN pay_input_values_f pivf ON pivf.input_value_id = prrv.input_value_id
    JOIN pay_element_types_f petf ON prr.element_type_id = petf.element_type_id
    JOIN pay_element_classifications pec ON petf.classification_id = pec.classification_id
    WHERE pivf.name = 'Pay Value'
        AND petf.business_group_id = 81
        AND ppa.date_earned = TO_DATE(:p_payroll_date, 'YYYY-MM-DD')
        AND ppa.assignment_set_id = NVL(:p_assignment_set_id, ppa.assignment_set_id)
        AND pec.classification_name LIKE '%Deduction%'
        AND petf.element_name NOT IN (
            'TAX1', 'AB', 'Bonus', 'HQ_House_Accomodation', 
            'House Rent Deduction', 'House Rent', 'Int Allowance', 
            'Planning and Engineering Allowance', 'TAX', 'Bonus Tax'
        )
    GROUP BY petf.element_name
    ORDER BY petf.element_name
    """
    
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
    # 3. Your updated SQL Query for Deductions
    sql = """
    SELECT 
        CASE 
            WHEN GROUPING(petf.element_name) = 1 THEN 'TOTAL DEDUCTIONS'
            ELSE petf.element_name
        END AS salary_head,
        SUM(NVL(prrv.result_value,0)) AS Salary_Head
    FROM pay_payroll_actions ppa
    JOIN pay_assignment_actions paa ON paa.payroll_action_id = ppa.payroll_action_id
    JOIN pay_run_results prr ON prr.assignment_action_id = paa.assignment_action_id
    JOIN pay_run_result_values prrv ON prrv.run_result_id = prr.run_result_id
    JOIN pay_input_values_f pivf ON pivf.input_value_id = prrv.input_value_id
    JOIN pay_element_types_f petf ON prr.element_type_id = petf.element_type_id
    JOIN pay_element_classifications pec ON petf.classification_id = pec.classification_id
    WHERE pivf.name = 'Pay Value'
        AND petf.business_group_id = 81
        AND ppa.date_earned = TO_DATE(:p_payroll_date, 'YYYY-MM-DD')
        AND ppa.assignment_set_id = NVL(:p_assignment_set_id, ppa.assignment_set_id)
        AND pec.classification_name LIKE '%Deduction%'
        AND petf.element_name NOT IN (
            'TAX1', 'AB', 'Bonus', 'HQ_House_Accomodation', 
            'House Rent Deduction', 'House Rent', 'Int Allowance', 
            'Planning and Engineering Allowance'
        )
    GROUP BY GROUPING SETS ((petf.element_name), ())
    ORDER BY CASE WHEN GROUPING(petf.element_name) = 1 THEN 1 ELSE 0 END, salary_head
    """
    
    # 4. Dictionary: Mapping Python variables to SQL :variables
    params = {
        "p_payroll_date": payroll_date, 
        "p_assignment_set_id": assignment_set_id if (assignment_set_id and assignment_set_id.strip() != "") else None
    }

    # 5. Execute using your run_query helper
    try:
        data = run_query(sql, params) 
        return jsonify(data)
    except Exception as e:
        print(f"Deductions Route Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/Payroll_Register')
def get_payroll_register():
    # Force the date to uppercase (e.g., '01-mar-2026' -> '01-MAR-2026')
    # This ensures it matches the 'MON' format in Oracle
    p_date = request.args.get('date', '01-MAR-2026').upper()

    params = {
        "p_emp_no": request.args.get('emp_no'),
        "p_payroll_date": p_date,  # This string goes into the TO_DATE function above
        "p_assignment_set_id": request.args.get('set_id'),
        "p_job_id": request.args.get('job_id'),
        "p_grade_id": request.args.get('grade_id'),
        "p_org_id": request.args.get('org_id'),
        "p_city": request.args.get('city')
    }

    try:
        # Call your run_query helper
        data = run_query(queries["Payroll_Register"], params)
        return jsonify(data)
    except Exception as e:
        # Return JSON error to avoid the '<' error in JS
        return jsonify({"error": str(e)}), 500





@app.route('/api/vacancy_pie_data')
def get_vacancy_pie_data():
    sql = queries.get("Vacancy")
    try:
        data = run_query(sql)
        # We find the final total row (e.g., "Total - SCALE 18" or a grand total)
        # or sum up the totals to get an overall company vacancy status
        total_working = 0
        total_vacant = 0
        
        for row in data:
            if "Total" in row['DESIGNATION']:
                total_working += float(row['WORKING'] or 0)
                total_vacant += float(row['VACANT'] or 0)
        
        return jsonify({
            "labels": ["Working", "Vacant"],
            "values": [total_working, total_vacant]
        })
    except Exception as e:
        print(f"Pie Chart Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/vacancy_summary')
def get_vacancy_summary():
    sql = queries.get("Vacancy")
    try:
        # Use your existing run_query helper
        data = run_query(sql) 
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500




    # 3. Your SQL Query
    sql_query = """
    SELECT DISTINCT
        papf.employee_number AS employee_number,
        papf.first_name ||' '|| papf.middle_names ||' '||papf.last_name AS employee_name,
        papf.national_identifier AS cnic,
        papf.attribute2 AS gp_fund,
        (SELECT name FROM hr_all_organization_units WHERE organization_id = paaf.organization_id) AS department,
        (SELECT name FROM per_positions WHERE position_id = paaf.position_id) AS position,
        (SELECT name FROM per_jobs WHERE job_id = paaf.job_id) AS designation,
        (SELECT name FROM per_grades WHERE grade_id = paaf.grade_id) AS grade,
        NVL(SUM(DECODE(petf.element_type_id, 121, prrv.result_value)), 0) AS basic_salary,
        SUM(DECODE(petf.element_type_id, 138, prrv.result_value)) AS personal_pay,
        SUM(DECODE(petf.element_type_id, 460, prrv.result_value)) AS DRA21,
        SUM(DECODE(petf.element_type_id, 478, prrv.result_value)) AS DRA22,
        SUM(DECODE(petf.element_type_id, 345, prrv.result_value)) AS ARA22,
        SUM(DECODE(petf.element_type_id, 458, prrv.result_value)) AS ARA23,
        SUM(DECODE(petf.element_type_id, 456, prrv.result_value)) AS ARA24,
        SUM(DECODE(petf.element_type_id, 999, prrv.result_value)) AS ARA25, 
        SUM(DECODE(petf.element_type_id, 888, prrv.result_value)) AS DRA25,
        SUM(DECODE(petf.element_type_id, 480, prrv.result_value)) AS house_rent_allowance,
        SUM(DECODE(petf.element_type_id, 129, prrv.result_value)) AS cash_medical_allowance,
        SUM(DECODE(petf.element_type_id, 146, prrv.result_value)) AS conveyance_allowance,
        SUM(DECODE(petf.element_type_id, 131, prrv.result_value)) AS hard_area_allowance,
        SUM(DECODE(petf.element_type_id, 141, prrv.result_value)) AS special_allowance,
        SUM(DECODE(petf.element_type_id, 142, prrv.result_value)) AS wapda_special_relief_allowance,
        SUM(DECODE(petf.element_type_id, 134, prrv.result_value)) AS integrated_allowance,
        SUM(DECODE(petf.element_type_id, 391, prrv.result_value)) AS Misc_Arrear,
        SUM(DECODE(petf.element_type_id, 387, prrv.result_value)) AS job_allowance,
        SUM(DECODE(petf.element_type_id, 221, prrv.result_value)) AS motor_cycle_allowance,
        SUM(DECODE(petf.element_type_id, 139, prrv.result_value)) AS qualification_pay,
        SUM(DECODE(petf.classification_id, 124, NVL(prrv.result_value, 0))) AS gross_pay,
        SUM(DECODE(petf.element_type_id, 151, prrv.result_value)) AS union_fund,
        SUM(DECODE(petf.element_type_id, 193, prrv.result_value)) AS income_tax,
        SUM(DECODE(petf.element_type_id, 152, prrv.result_value)) AS wapda_welfare_fund,
        SUM(DECODE(petf.element_type_id, 181, prrv.result_value)) AS gli_deduction,
        SUM(DECODE(petf.element_type_id, 202, prrv.result_value)) AS house_rent_deduction,
        SUM(DECODE(petf.element_type_id, 147, prrv.result_value)) AS bus_charges,
        SUM(DECODE(petf.element_type_id, 392, prrv.result_value)) AS govt_provident_fund,
        NVL(SUM(DECODE(petf.classification_id, 127, NVL(prrv.result_value, 0))), 0) AS total_deduction,
        NVL(SUM(DECODE(petf.classification_id, 124, NVL(prrv.result_value, 0))), 0) - 
        NVL(SUM(DECODE(petf.classification_id, 127, NVL(prrv.result_value, 0))), 0) AS net_salary
    FROM
        per_all_people_f papf,
        per_all_assignments_f paaf,
        per_periods_of_service ppos,
        hr_all_organization_units hou,
        pay_payroll_actions ppa,
        pay_assignment_actions paa,
        pay_element_types_f petf,
        pay_input_values_f pivf,
        pay_run_result_values prrv,
        pay_run_results prr,
        per_time_periods ptp
    WHERE 
        papf.person_id = paaf.person_id
        AND paa.assignment_id = paaf.assignment_id
        AND ppa.payroll_action_id = paa.payroll_action_id
        AND prr.assignment_action_id = paa.assignment_action_id
        AND petf.element_type_id = prr.element_type_id
        AND pivf.input_value_id = prrv.input_value_id
        AND prr.run_result_id = prrv.run_result_id
        AND pivf.name = 'Pay Value'
        AND (:p_org_id IS NULL OR paaf.organization_id = :p_org_id)
        AND (:p_assignment_set_id IS NULL OR ppa.assignment_set_id = :p_assignment_set_id)
       AND TO_DATE(ppa.date_earned) = TO_DATE(:p_payroll_date, 'DD-MON-YYYY')
    GROUP BY 
        papf.employee_number, papf.first_name, papf.middle_names, papf.last_name,
        papf.national_identifier, papf.attribute2, paaf.organization_id, 
        paaf.position_id, paaf.job_id, paaf.grade_id, ppa.date_earned
    """

    try:
        # 4. Parameters for Oracle

        params = {
           
            "p_assignment_set_id": p_assignment_set_id,
            "p_payroll_date": p_payroll_date
        }

        # Replace 'execute_query' with your actual database call function
        data = execute_query(sql_query, params) 
        
        # 5. Return as JSON
        return jsonify(data)

    except Exception as e:
        print(f"Error in bulk salary fetch: {str(e)}")
        return jsonify({"error": str(e)}), 500


def execute_query(sql, params):
    # Search for your existing connection variable
    # We try 'connection', then 'conn', then 'db'
    global_conn = globals().get('connection') or globals().get('conn') or globals().get('db')
    
    if global_conn is None:
        raise Exception("Database connection variable not found at top of app.py")

    cursor = global_conn.cursor()
    try:
        cursor.execute(sql, params)
        
        # Convert results to a list of dictionaries for JavaScript
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        return results
    except Exception as e:
        print(f"SQL Error: {e}")
        raise e
    finally:
        cursor.close()

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

        # Prepare parameters – all optional except date
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

if __name__ == "__main__":
    app.run(debug=True)
