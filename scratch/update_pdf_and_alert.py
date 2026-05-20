# Script to change date text color to black and simplify print confirmation alert

file_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Change date text color from #ad3333 to #1e293b (charcoal/black)
old_date_td = """                                    <div style='font-weight: 700; color: #1e293b; font-size: 10px;'>${capitalizedWeekday}</div>
                                    <div style='font-size: 11.5px; color: #ad3333; margin-top: 2px; font-weight: 800; letter-spacing: 0.25px;'>${dateYMD}</div>"""

new_date_td = """                                    <div style='font-weight: 700; color: #1e293b; font-size: 10px;'>${capitalizedWeekday}</div>
                                    <div style='font-size: 11.5px; color: #1e293b; margin-top: 2px; font-weight: 800; letter-spacing: 0.25px;'>${dateYMD}</div>"""

if old_date_td in content:
    content = content.replace(old_date_td, new_date_td)
    print("SUCCESS: Changed PDF session date color to black!")
else:
    print("WARNING: Could not find date td text block!")

# 2. Simplify the alert message to exactly: alert("Registro guardado");
old_alert = 'alert(`Registro de asistencia guardado como "${filename}.pdf"`);'
new_alert = 'alert("Registro guardado");'

if old_alert in content:
    content = content.replace(old_alert, new_alert)
    print("SUCCESS: Simplified print alert confirmation message!")
else:
    print("WARNING: Could not find old print alert block!")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS: PDF date color and alert simplified successfully!")
