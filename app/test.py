import pyodbc
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=10.20.55.21;"          
    "DATABASE=AI_IncidentDb;"
    "UID=sa;"
    "PWD=!nn0vation@321;"
)
print("Connected!")
conn.close()


