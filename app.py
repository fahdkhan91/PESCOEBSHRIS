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
import traceback

# ============================================================
# MOCK MODE ACTIVATION (ADDED FOR RENDER DEPLOYMENT)
# ============================================================
# Force mock mode on Render. Set to False if you deploy to a cloud with real DB access.
USE_MOCK_DB = True  # <-- CHANGE TO False IF YOU HAVE A REAL CLOUD ORACLE DB

if USE_MOCK_DB:
    print("⚠️  RUNNING IN MOCK MODE - Using fake database responses")
    print("   To use real Oracle DB, set USE_MOCK_DB = False and ensure network access")
else:
    print("✅ RUNNING IN REAL MODE - Attempting Oracle connection")
# ============================================================

# Original Oracle initialization function (preserved but guarded)
def init_oracle():
    if USE_MOCK_DB:
        print("Mock mode active - skipping Oracle client init")
        return
    
    try:
        if platform.system() == "Linux":
            lib_dir = os.path.join(os.getcwd(), "instantclient")
            oracledb.init_oracle_client(lib_dir=lib_dir)
        else:
            oracledb.init_oracle_client(lib_dir=r"C:\oracle\instantclient_23_0")
        print("Oracle Thick Mode initialized.")
    except Exception as e:
        print(f"Oracle Client Error: {e}")
        # Fallback to mock mode if Oracle init fails
        global USE_MOCK_DB
        USE_MOCK_DB = True
        print("Falling back to MOCK MODE due to Oracle client error")

# Call the original initialization (it will be skipped if USE_MOCK_DB is True)
init_oracle()

app = Flask(__name__)
app.secret_key = 'your_very_secret_key'

# ============================================================
# MODIFIED CONNECTION FUNCTION (with mock support)
# ============================================================
def get_db_connection():
    if USE_MOCK_DB:
        return MockConnection()
    
    try:
        connection = oracledb.connect(
            user="apps",
            password="appstest12",
            dsn="10.10.12.15:1521/PERPROD"
        )
        return connection
    except Exception as e:
        print(f"Oracle connection failed: {e}")
        # Fallback to mock mode if connection fails
        global USE_MOCK_DB
        USE_MOCK_DB = True
        return MockConnection()

# Global connection object (will be mock or real based on USE_MOCK_DB)
connection = get_db_connection()

# ============================================================
# ORIGINAL QUERIES DICTIONARY (COMPLETELY UNCHANGED)
# ============================================================
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

"Vacancy": r"""

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
s18_row4_ids AS (SELECT position_id FROM s18_position_data WHERE (UPPER(position_name
