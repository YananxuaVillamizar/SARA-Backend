# Script to add confirmation dialog to print flow in src/app/dashboard/asistencias/page.tsx

file_path = r"c:\Users\villa\sara-frontend\src\app\dashboard\asistencias\page.tsx"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update the print trigger block to show a confirm dialog before showing the alert
old_trigger = """        setTimeout(() => {
            iframe.contentWindow?.focus();
            iframe.contentWindow?.print();
            
            // Show custom alert right after print dialog disappears/completes
            alert("Registro guardado");
        }, 300);"""

new_trigger = """        setTimeout(() => {
            iframe.contentWindow?.focus();
            iframe.contentWindow?.print();
            
            // Ask user for confirmation to solve the native browser print/cancel detection limitation
            const guardado = confirm("¿Confirmar que el archivo fue guardado?");
            if (guardado) {
                alert("Registro guardado");
            }
        }, 300);"""

if old_trigger in content:
    content = content.replace(old_trigger, new_trigger)
    print("SUCCESS: Added print confirmation dialog successfully!")
else:
    print("WARNING: Could not find old print trigger block!")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESS: Print confirm flow updated successfully!")
